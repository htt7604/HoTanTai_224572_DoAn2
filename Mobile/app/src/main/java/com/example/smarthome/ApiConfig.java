package com.example.smarthome;

public final class ApiConfig {

    public static final String BASE_URL = "http://103.166.182.44:5000";

    private ApiConfig() {
    }

    public static String baseUrl() {
        return BASE_URL;
    }
}
