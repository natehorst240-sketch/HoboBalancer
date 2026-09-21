"""Port BalancerREF's main.cpp to the carrier: drop the charger and the supply ADC,
pick up the module's fuel gauge and LDO2-switched GPS rail.

Run once from BalancerCarrier/firmware/. Every edit asserts on its anchor, so a
changed upstream file fails loudly rather than half-applying.
"""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent / 'src' / 'main.cpp'
t = SRC.read_text(encoding='utf8')
n = 0


def sub(old, new, label):
    global t, n
    if old not in t:
        sys.exit(f'ANCHOR MISSING for {label!r} - upstream main.cpp has changed:\n  {old[:90]}')
    if t.count(old) != 1:
        sys.exit(f'anchor for {label!r} appears {t.count(old)} times, expected 1')
    t = t.replace(old, new)
    n += 1
    print(f'  {label}')


# ---- includes -------------------------------------------------------------
sub('#include "esp_adc/adc_oneshot.h"\n#include "esp_adc/adc_cali.h"\n'
    '#include "esp_adc/adc_cali_scheme.h"\n',
    '', 'dropped the three esp_adc includes')
sub('#include "esp_timer.h"',
    '#include "esp_timer.h"\n#include "driver/i2c_master.h"', 'added i2c_master.h')
sub('#include "board.hpp"', '#include "board.hpp"\n#include "fuelgauge.hpp"',
    'included fuelgauge.hpp') if '#include "board.hpp"' in t else None

# ---- globals --------------------------------------------------------------
sub('adc_oneshot_unit_handle_t adc;\nadc_cali_handle_t adcCalibration;\nbool adcReady=false;\n',
    '', 'dropped the ADC handles')

# ---- setupAdc -> fuel gauge + GPS rail ------------------------------------
old_adc = '''void setupAdc() {
    adc_oneshot_unit_init_cfg_t u{};u.unit_id=ADC_UNIT_2;
    if(adc_oneshot_new_unit(&u,&adc)!=ESP_OK)return;
    adc_oneshot_chan_cfg_t c{};c.atten=ADC_ATTEN_DB_12;c.bitwidth=ADC_BITWIDTH_DEFAULT;
    if(adc_oneshot_config_channel(adc,ADC_CHANNEL_1,&c)!=ESP_OK)return;
    adc_cali_curve_fitting_config_t cal{};cal.unit_id=ADC_UNIT_2;cal.chan=ADC_CHANNEL_1;
    cal.atten=ADC_ATTEN_DB_12;cal.bitwidth=ADC_BITWIDTH_DEFAULT;
    adcReady=adc_cali_create_scheme_curve_fitting(&cal,&adcCalibration)==ESP_OK;
}'''
new_power = '''// The FeatherS3[D] owns power. LDO2 (an NCP167BMX330TBG, 700 mA) feeds J4 pin 1, so
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
void setGpsPower(bool on){gpio_set_level(gpio_num_t(board::ldo2),on?1:0);}'''
sub(old_adc, new_power, 'setupAdc() -> setupPower() with LDO2 and the fuel gauge')

# ---- charger block --------------------------------------------------------
a = t.index('// BQ24075 input current limit and status.')
b = t.index('double supplyVolts() {')
charger = t[a:b]
assert 'setupCharger' in charger and 'inputPresent' in charger, 'charger block not as expected'
t = t[:a] + '''// There is no charger on the carrier: the FeatherS3[D] does charging itself, with a
// MAX17048 fuel gauge reporting the result over I2C. BalancerREF's setupCharger() and
// its EN1/EN2/PGOOD/CHG pins are gone. Leaving them would have been actively harmful -
// on this board GPIO5 is the acquire button and GPIO18 is the IIS3DWB's INT1, and that
// code drove both as outputs.
bool inputPresent(){return gpio_get_level(gpio_num_t(board::vbusSense))==1;}
bool charging(){return fuelgauge::charging();}
''' + t[b:]
n += 1
print('  removed setupCharger() and the BQ24075 pin readers')

# ---- supplyVolts ----------------------------------------------------------
old_sv = '''double supplyVolts() {
    if(!adcReady)return NAN;
    int raw,mv;
    if(adc_oneshot_read(adc,ADC_CHANNEL_1,&raw)!=ESP_OK ||
       adc_cali_raw_to_voltage(adcCalibration,raw,&mv)!=ESP_OK)return NAN;
    return 0.002*mv;
}'''
new_sv = '''// The cell itself, straight off the gauge, rather than BalancerREF's SYS_SW/2 on
// ADC2_CH1 - which shared its ADC unit with the radio and could not read the cell at
// all while charging.
double supplyVolts(){return fuelgauge::cellVolts();}'''
sub(old_sv, new_sv, 'supplyVolts() now reads the gauge')

# ---- status JSON ----------------------------------------------------------
sub('cJSON_AddBoolToObject(j,"input_present",inputPresent());cJSON_AddBoolToObject(j,"charging",charging());',
    'cJSON_AddBoolToObject(j,"input_present",inputPresent());cJSON_AddBoolToObject(j,"charging",charging());\n'
    '    num(j,"battery_soc_pct",fuelgauge::stateOfCharge());num(j,"battery_rate_pct_hr",fuelgauge::chargeRate());\n'
    '    cJSON_AddBoolToObject(j,"fuel_gauge_ok",fuelgauge::present());',
    'status JSON reports state of charge and gauge health')
sub('num(j,"supply_switched_v",supplyVolts());',
    'num(j,"battery_v",supplyVolts());',
    'renamed supply_switched_v -> battery_v (it is the cell now, not a switched rail)')

# ---- app_main -------------------------------------------------------------
sub('ESP_ERROR_CHECK(gpio_config(&out));setupEmitter();setupCharger();',
    'ESP_ERROR_CHECK(gpio_config(&out));setupEmitter();setupPower();',
    'app_main calls setupPower()')
sub('sensorOk=accel::setup();setupCapture();setupAdc();',
    'sensorOk=accel::setup();setupCapture();',
    'dropped the setupAdc() call')
sub('storage::mount();gps::start();',
    'storage::mount();setGpsPower(true);gps::start();',
    'GPS rail raised before gps::start()')

SRC.write_text(t, encoding='utf8')
print(f'\napplied {n} edits to {SRC.name}')
left = [w for w in ('adcReady', 'adc_oneshot', 'chgEn1', 'chgEn2', 'board::pgood',
                    'board::chgStat', 'setupCharger', 'supplyAdc', 'usbDm', 'usbDp')
        if w in t]
print('leftover BalancerREF-only symbols:', left or 'none')
if left:
    sys.exit(1)
