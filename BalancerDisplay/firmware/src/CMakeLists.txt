idf_component_register(SRCS "main.cpp" "display.cpp" "protocol.cpp"
    INCLUDE_DIRS "."
    REQUIRES driver esp_lcd esp_timer json esp_psram)
