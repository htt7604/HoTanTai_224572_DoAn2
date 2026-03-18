package com.example.smarthome;

import android.os.Bundle;
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import org.json.JSONObject;

import java.io.IOException;
import java.security.MessageDigest;
import java.util.Locale;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

public class RegisterActivity extends AppCompatActivity {

    private static final String PREFS_NAME = "smarthome_prefs";
    private static final String KEY_BASE_URL = "base_url";
    private static final String DEFAULT_BASE_URL = "http://10.0.2.2:5000";
    private static final MediaType JSON = MediaType.get("application/json; charset=utf-8");

    private final OkHttpClient httpClient = new OkHttpClient();

    private EditText etUsername;
    private EditText etPassword;
    private TextView tvStatus;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_register);

        etUsername = findViewById(R.id.etRegisterUsername);
        etPassword = findViewById(R.id.etRegisterPassword);
        tvStatus = findViewById(R.id.tvRegisterStatus);

        Button btnSubmit = findViewById(R.id.btnRegisterSubmit);
        Button btnBack = findViewById(R.id.btnRegisterBack);

        btnSubmit.setOnClickListener(v -> registerUser());
        btnBack.setOnClickListener(v -> finish());
    }

    private void registerUser() {
        String username = etUsername.getText().toString().trim().toLowerCase(Locale.US);
        String password = etPassword.getText().toString();
        if (username.isEmpty() || password.isEmpty()) {
            tvStatus.setText("Nhập tài khoản và mật khẩu");
            return;
        }

        JSONObject body = new JSONObject();
        try {
            body.put("username", username);
            body.put("password_hash", sha256Hex(password));
        } catch (Exception e) {
            tvStatus.setText("Lỗi tạo dữ liệu đăng ký");
            return;
        }

        tvStatus.setText("Đang tạo tài khoản...");

        Request request = new Request.Builder()
                .url(getBaseUrl() + "/auth/register")
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
                            tvStatus.setText("Tạo tài khoản thất bại: " + data.optString("error", "Lỗi"));
                            return;
                        }

                        tvStatus.setText("Tạo tài khoản thành công");
                        Toast.makeText(RegisterActivity.this, "Tạo tài khoản thành công", Toast.LENGTH_SHORT).show();
                        finish();
                    } catch (Exception e) {
                        tvStatus.setText("Lỗi parse phản hồi server");
                    }
                });
            }
        });
    }

    private String getBaseUrl() {
        String baseUrl = getSharedPreferences(PREFS_NAME, MODE_PRIVATE).getString(KEY_BASE_URL, DEFAULT_BASE_URL);
        if (baseUrl == null) return DEFAULT_BASE_URL;
        String trimmed = baseUrl.trim();
        if (trimmed.endsWith("/")) {
            trimmed = trimmed.substring(0, trimmed.length() - 1);
        }
        return trimmed.isEmpty() ? DEFAULT_BASE_URL : trimmed;
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
