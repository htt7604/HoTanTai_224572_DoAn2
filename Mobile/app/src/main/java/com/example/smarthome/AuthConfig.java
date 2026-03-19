package com.example.smarthome;

import android.content.Context;
import android.content.SharedPreferences;

import okhttp3.Request;

public final class AuthConfig {

    public static final String PREFS_NAME = "smarthome_prefs";
    public static final String KEY_AUTH_API_TOKEN = "auth_api_token";

    private AuthConfig() {
    }

    public static String getApiToken(Context context) {
        if (context == null) {
            return "";
        }
        SharedPreferences prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
        String token = prefs.getString(KEY_AUTH_API_TOKEN, "");
        return token == null ? "" : token.trim();
    }

    public static Request.Builder applyAuthHeader(Context context, Request.Builder builder) {
        String token = getApiToken(context);
        if (!token.isEmpty()) {
            builder.header("Authorization", "Bearer " + token);
        }
        return builder;
    }
}
