idf_component_register(SRCS "main.cpp" "measurement.cpp" "ble.cpp" "flightlog.cpp" "gps.cpp" "storage.cpp" "accel.cpp" "fuelgauge.cpp" "../vendor/iis3dwb_reg.c"
    INCLUDE_DIRS "." "../vendor"
    REQUIRES driver esp_driver_i2c esp_timer nvs_flash bt json spiffs esp_hw_support)
