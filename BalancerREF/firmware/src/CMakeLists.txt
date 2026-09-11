idf_component_register(SRCS "main.cpp" "measurement.cpp" "ble.cpp" "flightlog.cpp" "gps.cpp" "storage.cpp" "accel.cpp" "../vendor/iis3dwb_reg.c"
    INCLUDE_DIRS "." "../vendor"
    REQUIRES driver esp_timer nvs_flash bt json esp_adc spiffs esp_hw_support)
