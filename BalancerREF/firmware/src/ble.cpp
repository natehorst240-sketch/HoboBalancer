#include "ble.hpp"
#include <atomic>
#include <algorithm>
#include <cstring>
extern "C" {
#include "esp_err.h"
#include "nimble/nimble_port.h"
#include "nimble/nimble_port_freertos.h"
#include "host/ble_hs.h"
#include "host/ble_uuid.h"
#include "services/gap/ble_svc_gap.h"
#include "services/gatt/ble_svc_gatt.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
}
// Nordic UART UUIDs, conventional interoperable transport; newline-delimited JSON.
static const ble_uuid128_t serviceUuid=BLE_UUID128_INIT(0x9e,0xca,0xdc,0x24,0x0e,0xe5,0xa9,0xe0,0x93,0xf3,0xa3,0xb5,0x01,0x00,0x40,0x6e);
static const ble_uuid128_t rxUuid=BLE_UUID128_INIT(0x9e,0xca,0xdc,0x24,0x0e,0xe5,0xa9,0xe0,0x93,0xf3,0xa3,0xb5,0x02,0x00,0x40,0x6e);
static const ble_uuid128_t txUuid=BLE_UUID128_INIT(0x9e,0xca,0xdc,0x24,0x0e,0xe5,0xa9,0xe0,0x93,0xf3,0xa3,0xb5,0x03,0x00,0x40,0x6e);
static std::atomic<uint16_t> connection{BLE_HS_CONN_HANDLE_NONE};
static std::atomic<bool> subscribed{false};
static std::atomic<uint32_t> generation{0};
static uint16_t txHandle;
static uint8_t ownAddress;
static ble_gatt_chr_def characteristics[3]{};
static ble_gatt_svc_def services[2]{};
static void advertise();
static int access(uint16_t,uint16_t,ble_gatt_access_ctxt *ctx,void *) {
    if(ctx->op!=BLE_GATT_ACCESS_OP_WRITE_CHR) return BLE_ATT_ERR_UNLIKELY;
    char command[256]; const auto length=OS_MBUF_PKTLEN(ctx->om);
    if(!length || length>=sizeof(command)) return BLE_ATT_ERR_INVALID_ATTR_VALUE_LEN;
    if(os_mbuf_copydata(ctx->om,0,length,command)) return BLE_ATT_ERR_UNLIKELY;
    if(std::memchr(command,0,length)) return BLE_ATT_ERR_INVALID_ATTR_VALUE_LEN;
    return submit_command(command,length)?0:BLE_ATT_ERR_INSUFFICIENT_RES;
}
static int gap(ble_gap_event *e,void *) {
    switch(e->type) {
    case BLE_GAP_EVENT_CONNECT:
        if(e->connect.status==0) connection=e->connect.conn_handle; else advertise();
        break;
    case BLE_GAP_EVENT_DISCONNECT:
        connection=BLE_HS_CONN_HANDLE_NONE;subscribed=false;++generation;advertise();break;
    case BLE_GAP_EVENT_SUBSCRIBE:
        if(e->subscribe.attr_handle==txHandle) {subscribed=e->subscribe.cur_notify;++generation;}break;
    case BLE_GAP_EVENT_ADV_COMPLETE: advertise();break;
    default:break;
    }
    return 0;
}
static void advertise() {
    ble_hs_adv_fields f{};
    f.flags=BLE_HS_ADV_F_DISC_GEN|BLE_HS_ADV_F_BREDR_UNSUP;
    f.uuids128=const_cast<ble_uuid128_t*>(&serviceUuid);f.num_uuids128=1;f.uuids128_is_complete=1;
    if(ble_gap_adv_set_fields(&f)) return;
    ble_hs_adv_fields scan{};
    const char *name="BalancerREF";scan.name=(uint8_t*)name;scan.name_len=std::strlen(name);scan.name_is_complete=1;
    if(ble_gap_adv_rsp_set_fields(&scan)) return;
    ble_gap_adv_params p{};p.conn_mode=BLE_GAP_CONN_MODE_UND;p.disc_mode=BLE_GAP_DISC_MODE_GEN;
    ble_gap_adv_start(ownAddress,nullptr,BLE_HS_FOREVER,&p,gap,nullptr);
}
static void onSync() { if(!ble_hs_id_infer_auto(0,&ownAddress)) advertise(); }
static void reset(int) {connection=BLE_HS_CONN_HANDLE_NONE;subscribed=false;++generation;}
static void host(void *) {nimble_port_run();nimble_port_freertos_deinit();}
void ble_start() {
    ESP_ERROR_CHECK(nimble_port_init());
    ble_svc_gap_init();ble_svc_gatt_init();
    ble_svc_gap_device_name_set("BalancerREF");
    characteristics[0].uuid=&rxUuid.u;characteristics[0].access_cb=access;characteristics[0].flags=BLE_GATT_CHR_F_WRITE;
    characteristics[1].uuid=&txUuid.u;characteristics[1].access_cb=access;characteristics[1].flags=BLE_GATT_CHR_F_NOTIFY;characteristics[1].val_handle=&txHandle;
    services[0].type=BLE_GATT_SVC_TYPE_PRIMARY;services[0].uuid=&serviceUuid.u;services[0].characteristics=characteristics;
    ESP_ERROR_CHECK(ble_gatts_count_cfg(services));ESP_ERROR_CHECK(ble_gatts_add_svcs(services));
    ble_hs_cfg.sync_cb=onSync;ble_hs_cfg.reset_cb=reset;
    nimble_port_freertos_init(host);
}
bool ble_connected() {return connection!=BLE_HS_CONN_HANDLE_NONE;}
void ble_send_line(const char *line) {
    const uint16_t conn=connection.load(); const uint32_t epoch=generation.load();
    if(conn==BLE_HS_CONN_HANDLE_NONE || !subscribed) return;
    const size_t mtu=ble_att_mtu(conn), chunk=mtu>3?std::min(size_t(180),mtu-3):20;
    size_t sent=0,n=std::strlen(line);
    while(sent<n && connection==conn && subscribed && generation==epoch) {
        const size_t len=std::min(chunk,n-sent); bool ok=false;
        for(int retry=0;retry<4;retry++) {
            if(connection!=conn || generation!=epoch || !subscribed)return;
            os_mbuf *m=ble_hs_mbuf_from_flat(line+sent,len);
            if(m && !ble_gatts_notify_custom(conn,txHandle,m)) {ok=true;break;}
            vTaskDelay(pdMS_TO_TICKS(10));
        }
        if(!ok) { // terminate an incomplete line; receiver discards invalid JSON
            if(connection==conn && generation==epoch) {
                os_mbuf *m=ble_hs_mbuf_from_flat("\n",1);if(m) ble_gatts_notify_custom(conn,txHandle,m);
            }
            return;
        }
        sent+=len;vTaskDelay(pdMS_TO_TICKS(5));
    }
}
