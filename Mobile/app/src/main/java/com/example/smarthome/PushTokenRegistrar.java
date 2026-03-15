package com.example.smarthome;

import android.content.Context;
import android.content.SharedPreferences;

import org.json.JSONObject;

import java.io.IOException;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

public final class PushTokenRegistrar {

    private static final String PREFS_NAME = "smarthome_prefs";
    private static final String KEY_BASE_URL = "base_url";
    private static final String KEY_LAST_REGISTERED_TOKEN = "last_registered_fcm_token";
    private static final String DEFAULT_BASE_URL = "http://127.0.0.1:5000";
    private static final MediaType JSON = MediaType.get("application/json; charset=utf-8");
    private static final OkHttpClient HTTP = new OkHttpClient();

    private PushTokenRegistrar() {}

    public static void register(Context context, String token) {
        if (context == null || token == null || token.trim().isEmpty()) {
            return;
        }

        String trimmedToken = token.trim();
        SharedPreferences prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
        String lastToken = prefs.getString(KEY_LAST_REGISTERED_TOKEN, "");
        if (trimmedToken.equals(lastToken)) {
            return;
        }

        String baseUrl = prefs.getString(KEY_BASE_URL, DEFAULT_BASE_URL);
        if (baseUrl == null) {
            baseUrl = DEFAULT_BASE_URL;
        }
        baseUrl = sanitizeBaseUrl(baseUrl);
        if (baseUrl.contains("127.0.0.1") || baseUrl.contains("localhost")) {
            return;
        }

        try {
            JSONObject body = new JSONObject();
            body.put("token", trimmedToken);
            body.put("platform", "android");

            Request request = new Request.Builder()
                    .url(baseUrl + "/mobile/register-token")
                    .post(RequestBody.create(body.toString(), JSON))
                    .build();

            HTTP.newCall(request).enqueue(new Callback() {
                @Override
                public void onFailure(Call call, IOException e) {
                }

                @Override
                public void onResponse(Call call, Response response) {
                    if (response.isSuccessful()) {
                        prefs.edit().putString(KEY_LAST_REGISTERED_TOKEN, trimmedToken).apply();
                    }
                    response.close();
                }
            });
        } catch (Exception ignored) {
        }
    }

    private static String sanitizeBaseUrl(String value) {
        String trimmed = value.trim();
        if (trimmed.endsWith("/")) {
            trimmed = trimmed.substring(0, trimmed.length() - 1);
        }
        return trimmed;
    }
}
