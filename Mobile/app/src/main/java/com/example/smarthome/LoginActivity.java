package com.example.smarthome;

import android.content.Intent;
import android.os.Bundle;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import com.google.firebase.messaging.FirebaseMessaging;

import org.json.JSONObject;

import java.io.IOException;
import java.security.MessageDigest;
import java.util.Locale;
import java.util.concurrent.TimeUnit;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

public class LoginActivity extends AppCompatActivity {

    private static final String PREFS_NAME = AuthConfig.PREFS_NAME;
    private static final String KEY_AUTH_USERNAME = "auth_username";
    private static final String KEY_AUTH_PASSWORD_HASH = "auth_password_hash";
    private static final String KEY_AUTH_REMEMBER = "auth_remember";
    private static final String KEY_AUTH_LOGGED_IN = "auth_logged_in";
    private static final String KEY_AUTH_API_TOKEN = AuthConfig.KEY_AUTH_API_TOKEN;
    private static final MediaType JSON = MediaType.get("application/json; charset=utf-8");

        private final OkHttpClient httpClient = new OkHttpClient.Builder()
            .connectTimeout(5, TimeUnit.SECONDS)
            .readTimeout(8, TimeUnit.SECONDS)
            .writeTimeout(8, TimeUnit.SECONDS)
            .callTimeout(10, TimeUnit.SECONDS)
            .build();

    private EditText etUsername;
    private EditText etPassword;
    private CheckBox cbRemember;
    private TextView tvStatus;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_login);

        if (getSharedPreferences(PREFS_NAME, MODE_PRIVATE).getBoolean(KEY_AUTH_LOGGED_IN, false)) {
            Intent intent = new Intent(LoginActivity.this, MainActivity.class);
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
            startActivity(intent);
            finish();
            return;
        }

        bindViews();
        setupActions();
        loadSavedData();
        tryAutoLogin();
    }

    private void bindViews() {
        etUsername = findViewById(R.id.etLoginUsername);
        etPassword = findViewById(R.id.etLoginPassword);
        cbRemember = findViewById(R.id.cbLoginRemember);
        tvStatus = findViewById(R.id.tvLoginStatus);
    }

    private void setupActions() {
        Button btnLogin = findViewById(R.id.btnLogin);
        Button btnGoRegister = findViewById(R.id.btnGoRegister);
        Button btnGoChangePassword = findViewById(R.id.btnGoChangePassword);

        btnLogin.setOnClickListener(v -> loginManual());
        btnGoRegister.setOnClickListener(v -> startActivity(new Intent(this, RegisterActivity.class)));
        btnGoChangePassword.setOnClickListener(v -> startActivity(new Intent(this, ChangePasswordActivity.class)));
    }

    private void loadSavedData() {
        String username = getSharedPreferences(PREFS_NAME, MODE_PRIVATE).getString(KEY_AUTH_USERNAME, "");
        boolean remember = getSharedPreferences(PREFS_NAME, MODE_PRIVATE).getBoolean(KEY_AUTH_REMEMBER, false);

        etUsername.setText(username);
        cbRemember.setChecked(remember);
    }

    private void tryAutoLogin() {
        boolean remember = getSharedPreferences(PREFS_NAME, MODE_PRIVATE).getBoolean(KEY_AUTH_REMEMBER, false);
        String username = getSharedPreferences(PREFS_NAME, MODE_PRIVATE).getString(KEY_AUTH_USERNAME, "").trim().toLowerCase(Locale.US);
        String hash = getSharedPreferences(PREFS_NAME, MODE_PRIVATE).getString(KEY_AUTH_PASSWORD_HASH, "").trim().toLowerCase(Locale.US);

        if (!remember || username.isEmpty() || hash.length() != 64) {
            return;
        }

        tvStatus.setText("Đang tự động đăng nhập...");
        doLogin(username, hash, true);
    }

    private void loginManual() {
        String username = etUsername.getText().toString().trim().toLowerCase(Locale.US);
        String password = etPassword.getText().toString();
        if (username.isEmpty() || password.isEmpty()) {
            tvStatus.setText("Nhập tài khoản và mật khẩu");
            return;
        }

        doLogin(username, sha256Hex(password), cbRemember.isChecked());
    }

    private void doLogin(String username, String passwordHash, boolean remember) {
        tvStatus.setText("Đang đăng nhập...");

        JSONObject body = new JSONObject();
        try {
            body.put("username", username);
            body.put("password_hash", passwordHash);
        } catch (Exception e) {
            tvStatus.setText("Lỗi tạo dữ liệu đăng nhập");
            return;
        }

        Request request = new Request.Builder()
            .url(ApiConfig.baseUrl() + "/auth/login")
                .post(RequestBody.create(body.toString(), JSON))
                .build();

        httpClient.newCall(request).enqueue(new Callback() {
            @Override
            public void onFailure(Call call, IOException e) {
                runOnUiThread(() -> tvStatus.setText("Lỗi kết nối: " + e.getMessage()));
            }

            @Override
            public void onResponse(Call call, Response response) throws IOException {
                String responseBody = response.body() != null ? response.body().string() : "";
                runOnUiThread(() -> {
                    try {
                        JSONObject data = responseBody.isEmpty() ? new JSONObject() : new JSONObject(responseBody);
                        if (!response.isSuccessful() || !data.optBoolean("success", false)) {
                            String err = data.optString("error", "Sai thông tin");
                            tvStatus.setText("Đăng nhập thất bại (" + response.code() + "): " + err);
                            return;
                        }

                        String apiToken = data.optString("api_token", "").trim();
                        if (apiToken.isEmpty()) {
                            tvStatus.setText("Đăng nhập thất bại: server chưa trả api_token");
                            return;
                        }

                        getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
                                .edit()
                                .putString(KEY_AUTH_USERNAME, username)
                                .putBoolean(KEY_AUTH_LOGGED_IN, true)
                                .putBoolean(KEY_AUTH_REMEMBER, remember)
                                .putString(KEY_AUTH_API_TOKEN, apiToken)
                                .putString(KEY_AUTH_PASSWORD_HASH, remember ? passwordHash : "")
                                .apply();

                        FirebaseMessaging.getInstance().getToken()
                                .addOnCompleteListener(task -> {
                                    if (!task.isSuccessful()) {
                                        return;
                                    }
                                    String token = task.getResult();
                                    PushTokenRegistrar.register(getApplicationContext(), token, username, true);
                                });

                        etPassword.setText("");
                        tvStatus.setText("Đăng nhập thành công");
                        Toast.makeText(LoginActivity.this, "Đăng nhập thành công", Toast.LENGTH_SHORT).show();

                        Intent intent = new Intent(LoginActivity.this, MainActivity.class);
                        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
                        startActivity(intent);
                    } catch (Exception e) {
                        tvStatus.setText("Lỗi parse phản hồi server");
                    }
                });
            }
        });
    }

    private String sha256Hex(String input) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest((input == null ? "" : input).getBytes());
            StringBuilder builder = new StringBuilder();
            for (byte b : hash) {
                builder.append(String.format(Locale.US, "%02x", b));
            }
            return builder.toString();
        } catch (Exception e) {
            return "";
        }
    }
}
