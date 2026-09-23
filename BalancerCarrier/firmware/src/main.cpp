#include "board.hpp"
#include "fuelgauge.hpp"
#include "measurement.hpp"
#include "ble.hpp"
#include "flightlog.hpp"
#include "gps.hpp"
#include "storage.hpp"
#include "accel.hpp"
#include <atomic>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <algorithm>
extern "C" {
#include "driver/gpio.h"
#include "driver/ledc.h"
#include "driver/mcpwm_cap.h"
#include "driver/usb_serial_jtag.h"
#include "esp_timer.h"
#include "esp_sleep.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include "nvs.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "cJSON.h"
}
namespace {
constexpr char version[]="0.4.0-reference";
enum Kind:uint8_t { Drdy=0,Mag=1,Opt=2,Data=3 };
struct Capture {uint32_t tick;int64_t wall;Kind kind;};
struct Event {uint32_t tick;int64_t wall;Kind kind;float g[3];uint8_t clipped;};
struct Command {char text[256];};
struct Message {char text[3072];};
QueueHandle_t captureQueue,eventQueue,commandQueue,outputQueue;
std::atomic<uint32_t> captureLost{0},dataLost{0},ioErrors{0},timingErrors{0},outputLost{0};
std::atomic<bool> sensorOk{false};
std::atomic<float> liveG[3]{};
std::atomic<uint32_t> liveSampleMs{0};
double ticksPerSample=0; // capture ticks per 26.7 kHz accelerometer sample
uint32_t captureHz;
puck::Config configs[2];int profile=0;
const char *profileName() {return profile?"TR-VERT":"MR-VERT";}
struct SettingsV1 {uint32_t magic=0x42524631,version=1;int profile=0;puck::Config config[2];};
struct Settings {uint32_t magic=0x42524631,version=2;int profile=0;puck::Config config[2];bool flight=false;};
// Flight mode: autonomous continuous acquisition, GPS-tagged log, BLE off, sleep on no tach.
bool flightMode=false,usbPaused=false;
constexpr int64_t noTachSleepUs=180*1000000LL; // idle rotor for 3 minutes -> deep sleep
constexpr int64_t minAwakeUs=180*1000000LL;    // never sleep sooner than this after boot
int64_t lastTachSeen=0;
flight::Gate gate;
uint32_t lastFixSequence=0;
const char *wakeNote="power-on";
puck::Measurement measurement;
bool running=false,haveResult=false,continuous=false;
uint32_t sequence=0; // results emitted in the current continuous session
puck::Result lastResult;
puck::Config lastConfig;
int lastProfile=0;
uint32_t runId=0;
int64_t runStart=0,lastDrdy=0,lastTach=0;
uint32_t startCaptureLost=0,startDataLost=0,startIo=0,startTiming=0;
struct History {uint32_t run;double rpm,raw,phase;};
History history[2][20]{};unsigned historyCount[2]{};

void emit(cJSON *json) {
    Message m{};
    cJSON_AddStringToObject(json,"firmware",version);
    if(cJSON_PrintPreallocated(json,m.text,sizeof(m.text)-2,false)) {
        std::strcat(m.text,"\n");if(xQueueSend(outputQueue,&m,0)!=pdTRUE) ++outputLost;
    } else ++outputLost;
    cJSON_Delete(json);
}
void response(const char *type,const char *message) {
    auto *j=cJSON_CreateObject();cJSON_AddStringToObject(j,"type",type);
    cJSON_AddStringToObject(j,"message",message);emit(j);
}
void num(cJSON *j,const char *key,double v) {if(std::isfinite(v)) cJSON_AddNumberToObject(j,key,v);else cJSON_AddNullToObject(j,key);}
void configJson(cJSON *j,const puck::Config &c) {
    const char *axes[]={"X","Y","Z"};
    cJSON_AddStringToObject(j,"axis",axes[c.axis]);num(j,"sign",c.sign);num(j,"gain",c.gain);
    num(j,"phase_direction",c.phaseDirection);num(j,"phase_offset_deg",c.phaseOffsetDeg);
    num(j,"duration_s",c.durationS);num(j,"min_rpm",c.minRpm);num(j,"max_rpm",c.maxRpm);
    cJSON_AddBoolToObject(j,"axis_confirmed",c.axisConfirmed);
}
bool saveSettings() {
    Settings s;s.profile=profile;s.config[0]=configs[0];s.config[1]=configs[1];s.flight=flightMode;
    nvs_handle_t h;if(nvs_open("puck",NVS_READWRITE,&h)!=ESP_OK)return false;
    esp_err_t e=nvs_set_blob(h,"settings",&s,sizeof(s));if(e==ESP_OK)e=nvs_commit(h);nvs_close(h);return e==ESP_OK;
}
void loadSettings() {
    nvs_handle_t h; if(nvs_open("puck",NVS_READONLY,&h)!=ESP_OK)return;
    Settings s;size_t n=sizeof(s);const auto e=nvs_get_blob(h,"settings",&s,&n);nvs_close(h);
    if(e!=ESP_OK || s.magic!=0x42524631)return;
    if(n==sizeof(SettingsV1) && s.version==1)s.flight=false;          // upgrade from 0.2.0 settings
    else if(n!=sizeof(Settings) || s.version!=2)return;
    if((s.profile==0||s.profile==1) && puck::validConfig(s.config[0]) && puck::validConfig(s.config[1])) {
        configs[0]=s.config[0];configs[1]=s.config[1];profile=s.profile;flightMode=s.flight;
    }
}
// Rev C emitter: 20 kHz, 10 percent duty pulses into Q1 (about 500 mA peak through D1).
// The same signal, RC-delayed, gates the receiver comparator for synchronous detection.
constexpr uint32_t emitterHz=20000;constexpr uint32_t emitterDuty=102; // 10 bits: 102/1024 = 10 percent
void setupEmitter() {
    ledc_timer_config_t t{};t.speed_mode=LEDC_LOW_SPEED_MODE;t.timer_num=LEDC_TIMER_0;t.duty_resolution=LEDC_TIMER_10_BIT;
    t.freq_hz=emitterHz;t.clk_cfg=LEDC_AUTO_CLK;ESP_ERROR_CHECK(ledc_timer_config(&t));
    ledc_channel_config_t c{};c.speed_mode=LEDC_LOW_SPEED_MODE;c.channel=LEDC_CHANNEL_0;c.timer_sel=LEDC_TIMER_0;
    c.intr_type=LEDC_INTR_DISABLE;c.gpio_num=board::emitter;c.duty=0;c.hpoint=0;ESP_ERROR_CHECK(ledc_channel_config(&c));
}
void setEmitter(bool on) {
    ledc_set_duty(LEDC_LOW_SPEED_MODE,LEDC_CHANNEL_0,on?emitterDuty:0);ledc_update_duty(LEDC_LOW_SPEED_MODE,LEDC_CHANNEL_0);
}
bool IRAM_ATTR captureCallback(mcpwm_cap_channel_handle_t,const mcpwm_capture_event_data_t *data,void *ctx) {
    Capture c{data->cap_value,esp_timer_get_time(),*static_cast<Kind*>(ctx)};
    BaseType_t wake=pdFALSE;
    if(xQueueSendFromISR(captureQueue,&c,&wake)!=pdTRUE) captureLost.fetch_add(1,std::memory_order_relaxed);
    return wake==pdTRUE;
}
void setupCapture() {
    mcpwm_capture_timer_config_t t{};t.group_id=0;t.clk_src=MCPWM_CAPTURE_CLK_SRC_DEFAULT;
    mcpwm_cap_timer_handle_t timer;ESP_ERROR_CHECK(mcpwm_new_capture_timer(&t,&timer));
    ESP_ERROR_CHECK(mcpwm_capture_timer_get_resolution(timer,&captureHz));
    static Kind kinds[3]={Drdy,Mag,Opt};const int gpio[3]={board::drdy,board::mag,board::opt};
    for(int i=0;i<3;i++) {
        mcpwm_capture_channel_config_t c{};c.gpio_num=gpio[i];c.prescale=1;
        c.flags.pos_edge=i!=1;c.flags.neg_edge=i==1; // MAG leading low; OPT reflection high
        mcpwm_cap_channel_handle_t ch;ESP_ERROR_CHECK(mcpwm_new_capture_channel(timer,&c,&ch));
        mcpwm_capture_event_callbacks_t callbacks{};callbacks.on_cap=captureCallback;
        ESP_ERROR_CHECK(mcpwm_capture_channel_register_event_callbacks(ch,&callbacks,&kinds[i]));
        ESP_ERROR_CHECK(mcpwm_capture_channel_enable(ch));
    }
    ESP_ERROR_CHECK(mcpwm_capture_timer_enable(timer));ESP_ERROR_CHECK(mcpwm_capture_timer_start(timer));
}
void sensorTask(void *) {
    Capture c;
    for(;;) {
        if(xQueueReceive(captureQueue,&c,portMAX_DELAY)!=pdTRUE)continue;
        Event e{};e.tick=c.tick;e.wall=c.wall;e.kind=c.kind;
        if(c.kind==Drdy) {
            accel::Block b;unsigned n=0;
            if(!sensorOk || !accel::readBlock(b,n)) {++ioErrors;continue;}
            // A block read landing after the next watermark is stale. Never silently accept it.
            if(esp_timer_get_time()-c.wall>500) {++timingErrors;continue;}
            // The watermark marks the last sample of the block; the block mean sits (N-1)/2 samples earlier.
            e.tick=c.tick-uint32_t(ticksPerSample*(accel::decimation-1)/2.0+0.5);
            for(int a=0;a<3;a++) {e.g[a]=b.g[a];liveG[a]=b.g[a];}
            e.clipped=b.clipped;
            liveSampleMs=uint32_t(esp_timer_get_time()/1000);
            e.kind=Data;
        }
        if(xQueueSend(eventQueue,&e,0)!=pdTRUE) ++dataLost;
    }
}
// The FeatherS3[D] owns power. LDO2 (an NCP167BMX330TBG, 700 mA) feeds J4 pin 1, so
// the GPS is dead until this is raised - the default state is off, which is the safe
// direction. LDO2 also feeds the module's RGB LED and the second STEMMA connector.
// vbusSense reads the module's own USB-present divider and replaces BalancerREF's
// pgood pin.
void setupPower() {
    gpio_config_t o{};o.pin_bit_mask=1ULL<<board::ldo2;o.mode=GPIO_MODE_OUTPUT;
    ESP_ERROR_CHECK(gpio_config(&o));
    gpio_config_t i{};i.pin_bit_mask=1ULL<<board::vbusSense;i.mode=GPIO_MODE_INPUT;
    ESP_ERROR_CHECK(gpio_config(&i));
    fuelgauge::setup();          // logs and degrades to NAN readings if absent
}
void setGpsPower(bool on){gpio_set_level(gpio_num_t(board::ldo2),on?1:0);}
// There is no charger on the carrier: the FeatherS3[D] does charging itself, with a
// MAX17048 fuel gauge reporting the result over I2C. BalancerREF's setupCharger() and
// its EN1/EN2/PGOOD/CHG pins are gone. Leaving them would have been actively harmful -
// on this board GPIO5 is the acquire button and GPIO18 is the IIS3DWB's INT1, and that
// code drove both as outputs.
bool inputPresent(){return gpio_get_level(gpio_num_t(board::vbusSense))==1;}
bool charging(){return fuelgauge::charging();}
// The cell itself, straight off the gauge, rather than BalancerREF's SYS_SW/2 on
// ADC2_CH1 - which shared its ADC unit with the radio and could not read the cell at
// all while charging.
double supplyVolts(){return fuelgauge::cellVolts();}
void status() {
    auto *j=cJSON_CreateObject();cJSON_AddStringToObject(j,"type","status");
    cJSON_AddStringToObject(j,"profile",profileName());cJSON_AddBoolToObject(j,"acquiring",running);cJSON_AddBoolToObject(j,"continuous",continuous);num(j,"sequence",sequence);
    cJSON_AddBoolToObject(j,"sensor_ok",sensorOk);cJSON_AddBoolToObject(j,"reference_only",true);
    cJSON_AddBoolToObject(j,"ble_connected",ble_connected());num(j,"sample_rate_hz",accel::sampleRateHz);
    num(j,"full_scale_g",accel::fullScaleG);num(j,"lpf_nominal_hz",accel::odrHz/accel::lpfDivider);num(j,"decimation",accel::decimation);
    cJSON_AddStringToObject(j,"sensor","IIS3DWB SPI");num(j,"capture_hz",captureHz);
    num(j,"battery_v",supplyVolts());num(j,"output_drops",outputLost);
    cJSON_AddBoolToObject(j,"input_present",inputPresent());cJSON_AddBoolToObject(j,"charging",charging());
    num(j,"battery_soc_pct",fuelgauge::stateOfCharge());num(j,"battery_rate_pct_hr",fuelgauge::chargeRate());
    cJSON_AddBoolToObject(j,"fuel_gauge_ok",fuelgauge::present());
    num(j,"capture_drops",captureLost);num(j,"sample_queue_drops",dataLost);
    num(j,"i2c_errors",ioErrors);num(j,"late_reads",timingErrors);
    cJSON_AddBoolToObject(j,"flight",flightMode);cJSON_AddBoolToObject(j,"usb",usb_serial_jtag_is_connected());
    cJSON_AddStringToObject(j,"wake",wakeNote);
    auto *log=cJSON_AddObjectToObject(j,"log");cJSON_AddBoolToObject(log,"mounted",storage::mounted());
    num(log,"records",storage::records());num(log,"bytes",storage::used());num(log,"capacity",storage::total());
    cJSON_AddBoolToObject(log,"full",storage::full());num(log,"write_failures",storage::writeFailures());
    auto *g=cJSON_AddObjectToObject(j,"gps");const auto fix=gps::latest();
    cJSON_AddBoolToObject(g,"present",gps::present());cJSON_AddBoolToObject(g,"fix",fix.valid);
    num(g,"sats",fix.sats);num(g,"speed_mps",fix.speedMps);num(g,"course_deg",fix.courseDeg);
    num(g,"sentences",gps::sentences());num(g,"rejected",gps::rejected());num(g,"baud",gps::baud());
    char iso[24];if(flight::isoTime(fix,iso,sizeof(iso)))cJSON_AddStringToObject(g,"utc",iso);else cJSON_AddNullToObject(g,"utc");
    if(liveSampleMs && uint32_t(esp_timer_get_time()/1000)-liveSampleMs.load()<20) {
        auto *xyz=cJSON_AddArrayToObject(j,"latest_xyz_g");
        for(int a=0;a<3;a++)cJSON_AddItemToArray(xyz,cJSON_CreateNumber(liveG[a]));
    } else cJSON_AddNullToObject(j,"latest_xyz_g");
    auto *c=cJSON_AddObjectToObject(j,"config");configJson(c,configs[profile]);emit(j);
}
void resultJson(const puck::Result &r) {
    auto *j=cJSON_CreateObject();cJSON_AddStringToObject(j,"type","result");
    cJSON_AddBoolToObject(j,"reference_only",true);num(j,"run_id",runId);
    cJSON_AddStringToObject(j,"profile",profileName());cJSON_AddBoolToObject(j,"continuous",continuous);num(j,"sequence",sequence);
    cJSON_AddBoolToObject(j,"valid",r.valid);
    cJSON_AddBoolToObject(j,"stable",r.stable);cJSON_AddBoolToObject(j,"phase_valid",r.phaseValid);
    cJSON_AddBoolToObject(j,"direction_valid",r.directionValid);
    cJSON_AddStringToObject(j,"quality",r.quality==puck::Quality::StableVector?"stable_vector":
        r.quality==puck::Quality::DirectionOnly?"direction_only":"unreliable");
    if(r.flags&puck::Clipping)cJSON_AddStringToObject(j,"message","overrange on selected axis; check mounting and repeat");
    num(j,"flags",r.flags);num(j,"rpm",r.rpm);num(j,"rpm_cv",r.rpmCv);
    num(j,"revolutions",r.revolutions);num(j,"samples",r.samples);num(j,"rejected_tach_edges",r.rejectedEdges);
    num(j,"raw_vector_scatter_ips_peak",r.vectorScatter);num(j,"raw_amplitude_scatter_ips_peak",r.amplitudeScatter);
    num(j,"per_rev_phase_scatter_deg",r.phaseScatterDeg);
    auto *axes=cJSON_AddArrayToObject(j,"raw_axes");const char *names[]={"X","Y","Z"};
    for(int a=0;a<3;a++) {
        auto *v=cJSON_CreateObject();cJSON_AddStringToObject(v,"axis",names[a]);
        num(v,"ips_peak",r.rawPeak[a]);num(v,"ips_rms",r.rawPeak[a]/std::sqrt(2.0));
        num(v,"velocity_phase_deg",r.rawPhase[a]);num(v,"dc_g",r.dcG[a]);
        cJSON_AddBoolToObject(v,"clipped",(r.clippedAxes>>a)&1);cJSON_AddItemToArray(axes,v);
    }
    num(j,"adjusted_ips_peak",r.peak);num(j,"adjusted_ips_rms",r.rms);
    // Direction-only runs keep their phase for rough correction; calibration still needs phase_valid.
    if(r.directionValid)num(j,"adjusted_velocity_phase_deg",r.phase);else cJSON_AddNullToObject(j,"adjusted_velocity_phase_deg");
    num(j,"signed_acceleration_phase_deg",r.accelerationPhase);
    cJSON_AddStringToObject(j,"raw_phase_definition","positive velocity peak after selected tach edge; time-forward degrees");
    auto *c=cJSON_AddObjectToObject(j,"config");configJson(c,configs[profile]);
    const unsigned n=historyCount[profile];
    if(r.stable && n && std::abs(history[profile][(n-1)%20].rpm-r.rpm)/r.rpm<0.02)
        num(j,"raw_delta_ips_peak",r.rawPeak[configs[profile].axis]-history[profile][(n-1)%20].raw);
    else cJSON_AddNullToObject(j,"raw_delta_ips_peak");
    emit(j);
    if(r.stable) {
        history[profile][n%20]={runId,r.rpm,r.rawPeak[configs[profile].axis],r.rawPhase[configs[profile].axis]};
        ++historyCount[profile];
    }
}
void logWindow(const puck::Result &r) {
    if(!flightMode || (r.flags&puck::Cancelled))return;
    const auto &c=configs[profile];
    flight::Record rec;rec.seq=sequence;rec.run=runId;rec.flags=r.flags;rec.uptimeMs=uint32_t(esp_timer_get_time()/1000);
    rec.profile=profileName();rec.valid=r.valid;rec.stable=r.stable;rec.phaseValid=r.phaseValid;
    rec.rpm=r.rpm;rec.rpmCv=r.rpmCv;rec.scatter=r.vectorScatter;rec.axis=c.axis;rec.sign=c.sign;
    for(int a=0;a<3;a++){rec.peak[a]=r.rawPeak[a];rec.phase[a]=r.rawPhase[a];rec.dc[a]=r.dcG[a];}
    rec.fix=gps::latest();rec.fixes=gate.fixes();rec.speedMean=gate.meanSpeed();
    rec.speedSpread=gate.speedSpread();rec.courseSpread=gate.courseSpreadDeg();
    rec.level=gate.level(r.dcG[c.axis]*c.sign,r.stable);
    char line[640];
    if(flight::formatRecord(rec,line,sizeof(line)))storage::append(line);
}
void logBoot() {
    flight::Record rec;rec.type="boot";rec.uptimeMs=uint32_t(esp_timer_get_time()/1000);rec.note=wakeNote;rec.fix=gps::latest();
    char line[200];if(flight::formatRecord(rec,line,sizeof(line)))storage::append(line);
}
void beginRun() {
    gate.reset();
    measurement.begin(configs[profile],captureHz);++runId;running=true;haveResult=false;
    runStart=esp_timer_get_time();lastTach=lastDrdy=0;
    startCaptureLost=captureLost;startDataLost=dataLost;startIo=ioErrors;startTiming=timingErrors;
}
// repeat=true keeps acquiring back to back until stop, the button, or a sensor failure.
void startRun(bool repeat=false) {
    if(running) {response("error","already acquiring");return;}
    if(!sensorOk) {response("error","IIS3DWB initialization failed; check SPI wiring and reboot");return;}
    continuous=repeat;sequence=0;beginRun();
    auto *j=cJSON_CreateObject();cJSON_AddStringToObject(j,"type","started");
    cJSON_AddStringToObject(j,"message",profileName());cJSON_AddStringToObject(j,"profile",profileName());
    cJSON_AddBoolToObject(j,"continuous",continuous);num(j,"duration_s",configs[profile].durationS);emit(j);
}
void finishRun(bool cancelled=false) {
    if(!running)return;
    if(captureLost!=startCaptureLost || dataLost!=startDataLost)measurement.fault(puck::QueueOverflow);
    if(ioErrors!=startIo)measurement.fault(puck::IoError);
    if(timingErrors!=startTiming)measurement.fault(puck::TimingError);
    if(!lastDrdy || esp_timer_get_time()-lastDrdy>5000)measurement.fault(puck::SampleGap);
    if(cancelled)measurement.fault(puck::Cancelled);
    const double timeoutUs=measurement.tachTimeoutSeconds()*1e6;
    lastResult=measurement.finish(lastTach && esp_timer_get_time()-lastTach<timeoutUs);
    running=false;haveResult=true;lastConfig=configs[profile];lastProfile=profile;
    if(continuous)++sequence;
    resultJson(lastResult);
    logWindow(lastResult);
    if(cancelled)continuous=false;
    // Sampling never stops between windows, so the next window starts immediately.
    if(continuous) {
        if(sensorOk)beginRun();
        else {continuous=false;response("error","sensor failure ended continuous acquisition");}
    }
}
// Deep sleep wakes on EXT1: a magnetic tach pulse (rotor spin-up) or an acquire-button press.
// The optical profile has no wake source while the emitter is off; flight logging uses MR-VERT.
void goToSleep() {
    if(running)finishRun(true);
    storage::sync();gps::sleep();
    gpio_set_level(gpio_num_t(board::led),0);setEmitter(false);
    accel::powerDown();
    // MAG_TACH (LM1815 open collector, 5.6k pull-up) and the acquire button both idle high and pulse low.
    esp_sleep_enable_ext1_wakeup((1ULL<<board::mag)|(1ULL<<board::acquire),ESP_EXT1_WAKEUP_ANY_LOW);
    esp_deep_sleep_start();
}
void changeProfile(int p) {
    if(p==profile) {response("profile",profileName());return;}
    const int old=profile;profile=p;
    if(!saveSettings()) {profile=old;response("error","NVS save failed; profile unchanged");return;}
    setEmitter(profile==1);
    haveResult=false;response("profile",profileName());
}
bool readNumber(cJSON *j,const char *key,double &out) {
    auto *v=cJSON_GetObjectItemCaseSensitive(j,key);if(!v)return true;
    if(!cJSON_IsNumber(v) || !std::isfinite(v->valuedouble))return false;
    out=v->valuedouble;return true;
}
bool allowedKeys(cJSON *j,const char *const *keys) {
    for(auto *v=j->child;v;v=v->next) {
        bool found=false;
        for(int i=0;keys[i];i++)if(!std::strcmp(v->string,keys[i]))found=true;
        if(!found)return false;
        for(auto *w=v->next;w;w=w->next)if(!std::strcmp(v->string,w->string))return false;
    }
    return true;
}
void command(const char *text) {
    const char *end=nullptr;auto *j=cJSON_ParseWithOpts(text,&end,true);
    if(!j || !cJSON_IsObject(j)) {cJSON_Delete(j);response("error","expected one complete JSON object");return;}
    auto *cmd=cJSON_GetObjectItemCaseSensitive(j,"cmd");
    if(!cJSON_IsString(cmd)) {cJSON_Delete(j);response("error","missing cmd");return;}
    const char *op=cmd->valuestring;
    static const char *simpleKeys[]={"cmd",nullptr};
    static const char *profileKeys[]={"cmd","value",nullptr};
    static const char *startKeys[]={"cmd","continuous",nullptr};
    static const char *flightKeys[]={"cmd","value",nullptr};
    static const char *configKeys[]={"cmd","axis","sign","gain","phase_direction","phase_offset_deg","duration_s","min_rpm","max_rpm",nullptr};
    static const char *compareKeys[]={"cmd","reference_ips_peak","reference_phase_deg",nullptr};
    const char *const *keys=!std::strcmp(op,"config")?configKeys:!std::strcmp(op,"profile")?profileKeys:
        !std::strcmp(op,"compare")?compareKeys:!std::strcmp(op,"start")?startKeys:!std::strcmp(op,"flight")?flightKeys:simpleKeys;
    if(!allowedKeys(j,keys)){cJSON_Delete(j);response("error","unknown or duplicate command field");return;}
    if(!std::strcmp(op,"status"))status();
    else if(!std::strcmp(op,"start")) {
        auto *repeat=cJSON_GetObjectItemCaseSensitive(j,"continuous");
        if(repeat && !cJSON_IsBool(repeat))response("error","continuous must be true or false");
        else startRun(repeat && cJSON_IsTrue(repeat));
    }
    else if(!std::strcmp(op,"stop")) {if(running)finishRun(true);else response("error","not acquiring");}
    else if(running) response("error","configuration and history commands require idle state");
    else if(!std::strcmp(op,"profile")) {
        auto *v=cJSON_GetObjectItemCaseSensitive(j,"value");
        if(cJSON_IsString(v) && (!std::strcmp(v->valuestring,"MR-VERT") || !std::strcmp(v->valuestring,"TR-VERT")))
            changeProfile(!std::strcmp(v->valuestring,"TR-VERT"));
        else response("error","profile must be MR-VERT or TR-VERT");
    } else if(!std::strcmp(op,"config")) {
        auto c=configs[profile];double sign=c.sign,direction=c.phaseDirection;bool ok=true;
        auto *axis=cJSON_GetObjectItemCaseSensitive(j,"axis");
        if(axis) {
            if(!cJSON_IsString(axis) || std::strlen(axis->valuestring)!=1 || !std::strchr("XYZ",axis->valuestring[0]))ok=false;
            else {c.axis=axis->valuestring[0]=='X'?0:axis->valuestring[0]=='Y'?1:2;c.axisConfirmed=true;}
        }
        ok &= readNumber(j,"sign",sign) && readNumber(j,"phase_direction",direction) &&
            readNumber(j,"gain",c.gain) && readNumber(j,"phase_offset_deg",c.phaseOffsetDeg) &&
            readNumber(j,"duration_s",c.durationS) && readNumber(j,"min_rpm",c.minRpm) && readNumber(j,"max_rpm",c.maxRpm);
        if((sign!=1 && sign!=-1)||(direction!=1 && direction!=-1))ok=false;
        c.sign=sign==1?1:-1;c.phaseDirection=direction==1?1:-1;
        if(!ok || !puck::validConfig(c))response("error","invalid config; see documented bounds");
        else {
            auto old=configs[profile];configs[profile]=c;
            if(!saveSettings()){configs[profile]=old;response("error","NVS save failed; config unchanged");}
            else {haveResult=false;historyCount[profile]=0;status();}
        }
    } else if(!std::strcmp(op,"compare")) {
        auto *ips=cJSON_GetObjectItemCaseSensitive(j,"reference_ips_peak");
        auto *phase=cJSON_GetObjectItemCaseSensitive(j,"reference_phase_deg");
        if(!haveResult || lastProfile!=profile || !lastResult.phaseValid)
            response("error","need a stable completed run with confirmed axis and usable phase");
        else if(!cJSON_IsNumber(ips)||!cJSON_IsNumber(phase)||!std::isfinite(ips->valuedouble)||
                !std::isfinite(phase->valuedouble)||ips->valuedouble<=0||phase->valuedouble<0||phase->valuedouble>=360)
            response("error","supply positive reference_ips_peak and reference_phase_deg in [0,360)");
        else {
            const int a=lastConfig.axis;auto *out=cJSON_CreateObject();cJSON_AddStringToObject(out,"type","comparison_proposal");
            num(out,"run_id",runId);num(out,"gain",ips->valuedouble/lastResult.rawPeak[a]);
            const double raw=lastResult.rawPhase[a]+(lastConfig.sign<0?180:0);
            num(out,"phase_offset_deg",puck::wrapDegrees(phase->valuedouble-lastConfig.phaseDirection*raw+180)-180);
            cJSON_AddBoolToObject(out,"applied",false);cJSON_AddStringToObject(out,"note","single pair only; verify repeated matched-RPM readings before explicit config");emit(out);
        }
    } else if(!std::strcmp(op,"flight")) {
        auto *v=cJSON_GetObjectItemCaseSensitive(j,"value");
        if(!cJSON_IsBool(v))response("error","flight value must be true or false");
        else {
            const bool old=flightMode;flightMode=cJSON_IsTrue(v);
            if(!saveSettings()){flightMode=old;response("error","NVS save failed; flight mode unchanged");}
            else {usbPaused=false;status();}
        }
    } else if(!std::strcmp(op,"download")) {
        auto *head=cJSON_CreateObject();cJSON_AddStringToObject(head,"type","download_begin");
        num(head,"records",storage::records());num(head,"bytes",storage::used());emit(head);
        const bool ok=storage::stream([](const char *line,void *){
            Message m{};std::strncpy(m.text,line,sizeof(m.text)-1);xQueueSend(outputQueue,&m,portMAX_DELAY);},nullptr);
        auto *tail=cJSON_CreateObject();cJSON_AddStringToObject(tail,"type","download_end");
        cJSON_AddBoolToObject(tail,"complete",ok);num(tail,"records",storage::records());
        cJSON_AddStringToObject(tail,"firmware",version);
        Message m{};
        if(cJSON_PrintPreallocated(tail,m.text,sizeof(m.text)-2,false)){std::strcat(m.text,"\n");xQueueSend(outputQueue,&m,portMAX_DELAY);}
        cJSON_Delete(tail);
    } else if(!std::strcmp(op,"erase")) {
        if(storage::erase())status();else response("error","erase failed");
    } else if(!std::strcmp(op,"history")) {
        auto *out=cJSON_CreateObject();cJSON_AddStringToObject(out,"type","history");cJSON_AddStringToObject(out,"profile",profileName());
        auto *runs=cJSON_AddArrayToObject(out,"runs");const unsigned n=historyCount[profile];
        for(unsigned i=n>20?n-20:0;i<n;i++) {
            auto *v=cJSON_CreateObject();const auto &h=history[profile][i%20];num(v,"run_id",h.run);num(v,"rpm",h.rpm);
            num(v,"raw_ips_peak",h.raw);num(v,"raw_velocity_phase_deg",h.phase);cJSON_AddItemToArray(runs,v);
        }emit(out);
    } else response("error","unknown cmd: status/start/stop/profile/config/compare/history/flight/download/erase");
    cJSON_Delete(j);
}
void analysisTask(void *) {
    Event e;Command cmd;int previous=1,debounced=1;int64_t changed=0,pressed=0;bool longDone=false;
    for(;;) {
        // Process bounded batches so continuous sampling cannot starve commands/buttons.
        for(int i=0;i<64 && xQueueReceive(eventQueue,&e,0)==pdTRUE;i++) {
            if(e.kind==(profile?Opt:Mag))lastTachSeen=e.wall;
            if(!running || e.wall<runStart)continue;
            if(e.kind==Data) {
                lastDrdy=e.wall;puck::Sample s{e.tick,{e.g[0],e.g[1],e.g[2]},e.clipped};measurement.sample(s);
            } else if(e.kind==(profile?Opt:Mag) && measurement.tach(e.tick))lastTach=e.wall;
        }
        if(xQueueReceive(commandQueue,&cmd,0)==pdTRUE)command(cmd.text);
        const int64_t now=esp_timer_get_time();
        if(const uint32_t fs=gps::fixSequence();fs!=lastFixSequence){lastFixSequence=fs;if(running)gate.add(gps::latest());}
        if(running && now-runStart>=int64_t(configs[profile].durationS*1e6))finishRun();
        if(flightMode) {
            // USB plugged in = bench/download session: pause autonomous acquisition and never sleep.
            const bool usb=usb_serial_jtag_is_connected();
            if(usb) {
                if(!usbPaused){usbPaused=true;if(running && continuous)finishRun(true);}
            } else {
                usbPaused=false;
                if(!running && sensorOk && !storage::full())startRun(true);
                if(now>minAwakeUs && now-lastTachSeen>noTachSleepUs)goToSleep();
            }
        }
        const int level=gpio_get_level(gpio_num_t(board::acquire));
        if(level!=previous){changed=now;previous=level;}
        if(now-changed>30000 && level!=debounced) {
            debounced=level;
            if(!level){pressed=now;longDone=false;}
            else if(!longDone && !flightMode){if(running)finishRun(true);else startRun();}
        }
        if(!debounced && !longDone && now-pressed>2000000) {
            longDone=true;if(running)response("error","stop acquisition before changing profile");else changeProfile(1-profile);
        }
        bool on;
        if(!sensorOk || (haveResult && !lastResult.valid)) on=(now/100000)%2;
        else if(running)on=(now/250000)%2;
        else if(haveResult && lastResult.stable)on=true;
        else if(haveResult)on=(now/150000)%2;
        else on=ble_connected()?((now%2000000)<150000):((now%3000000)<80000);
        gpio_set_level(gpio_num_t(board::led),on);
        vTaskDelay(pdMS_TO_TICKS(1));
    }
}
}
bool submit_command(const char *s,size_t len) {
    if(!commandQueue || len==0 || len>=sizeof(Command::text))return false;
    Command c{};std::memcpy(c.text,s,len);return xQueueSend(commandQueue,&c,0)==pdTRUE;
}
extern "C" void app_main() {
    gpio_config_t out{};out.pin_bit_mask=(1ULL<<board::led);out.mode=GPIO_MODE_OUTPUT;
    ESP_ERROR_CHECK(gpio_config(&out));setupEmitter();setupPower();
    gpio_config_t in{};in.pin_bit_mask=1ULL<<board::acquire;in.mode=GPIO_MODE_INPUT;in.pull_up_en=GPIO_PULLUP_ENABLE;
    ESP_ERROR_CHECK(gpio_config(&in));
    usb_serial_jtag_driver_config_t usb{};usb.rx_buffer_size=512;usb.tx_buffer_size=4096;
    ESP_ERROR_CHECK(usb_serial_jtag_driver_install(&usb));
    const esp_err_t nvs=nvs_flash_init(); // never silently erase calibration/settings
    if(nvs==ESP_OK)loadSettings();
    captureQueue=xQueueCreate(64,sizeof(Capture));eventQueue=xQueueCreate(256,sizeof(Event));
    commandQueue=xQueueCreate(4,sizeof(Command));outputQueue=xQueueCreate(4,sizeof(Message));
    configASSERT(captureQueue && eventQueue && commandQueue && outputQueue);
    switch(esp_sleep_get_wakeup_cause()){case ESP_SLEEP_WAKEUP_EXT1:wakeNote="wake:tach-or-button";break;
        case ESP_SLEEP_WAKEUP_UNDEFINED:wakeNote="power-on";break;default:wakeNote="wake:other";}
    sensorOk=accel::setup();setupCapture();ticksPerSample=double(captureHz)/accel::odrHz;
    storage::mount();setGpsPower(true);gps::start();
    setEmitter(profile==1);
    configASSERT(xTaskCreatePinnedToCore(sensorTask,"sensor",4096,nullptr,22,nullptr,1)==pdPASS);
    if(sensorOk && !accel::start())sensorOk=false;
    // Let the filter settle and drain initial timing transients before accepting runs.
    vTaskDelay(pdMS_TO_TICKS(100));
    if(!flightMode)ble_start();   // flight mode: nothing to talk to in the air; BLE returns on reboot
    lastTachSeen=esp_timer_get_time();
    if(flightMode)logBoot();
    response("boot","BalancerREF reference firmware; send {\"cmd\":\"status\"}");
    if(nvs!=ESP_OK)response("error","NVS initialization failed; defaults active, persistent settings unavailable");
    configASSERT(xTaskCreatePinnedToCore(analysisTask,"analysis",12288,nullptr,8,nullptr,1)==pdPASS);
    char line[256];unsigned used=0;bool overflow=false;Message message;
    for(;;) {
        char bytes[64];const int n=usb_serial_jtag_read_bytes(bytes,sizeof(bytes),0);
        for(int i=0;i<n;i++) {
            const char c=bytes[i];if(c=='\r')continue;
            if(c=='\n') {
                if(!overflow && used && !submit_command(line,used))response("error","command queue busy");
                if(overflow)response("error","command too long or contains NUL");
                used=0;overflow=false;
            } else if(c==0 || used>=sizeof(line)-1)overflow=true;
            else if(!overflow)line[used++]=c;
        }
        if(xQueueReceive(outputQueue,&message,0)==pdTRUE) {
            const size_t length=std::strlen(message.text);
            const int sent=usb_serial_jtag_write_bytes(message.text,length,pdMS_TO_TICKS(20));
            if(sent<int(length)) {++outputLost;usb_serial_jtag_write_bytes("\n",1,pdMS_TO_TICKS(5));}
            ble_send_line(message.text);
        }
        vTaskDelay(pdMS_TO_TICKS(5));
    }
}
