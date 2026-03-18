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

public class ChangePasswordActivity extends AppCompatActivity {

    private static final String PREFS_NAME = "smarthome_prefs";
    private static final String KEY_BASE_URL = "base_url";
    private static final String DEFAULT_BASE_URL = "http://10.0.2.2:5000";
    private static final MediaType JSON = MediaType.get("application/json; charset=utf-8");

    private final OkHttpClient httpClient = new OkHttpClient();

    private EditText etUsername;
    private EditText etOldPassword;
    private EditText etNewPassword;
    private TextView tvStatus;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_change_password);

        etUsername = findViewById(R.id.etChangeUsername);
        etOldPassword = findViewById(R.id.etChangeOldPassword);
        etNewPassword = findViewById(R.id.etChangeNewPassword);
        tvStatus = findViewById(R.id.tvChangeStatus);

        Button btnSubmit = findViewById(R.id.btnChangeSubmit);
        Button btnBack = findViewById(R.id.btnChangeBack);

        btnSubmit.setOnClickListener(v -> changePassword());
        btnBack.setOnClickListener(v -> finish());
    }

    private void changePassword() {
        String username = etUsername.getText().toString().trim().toLowerCase(Locale.US);
        String oldPassword = etOldPassword.getText().toString();
        String newPassword = etNewPassword.getText().toString();

        if (username.isEmpty() || oldPassword.isEmpty() || newPassword.isEmpty()) {
            tvStatus.setText("Nhập đủ tài khoản + mật khẩu cũ + mật khẩu mới");
            return;
        }

        JSONObject body = new JSONObject();
        try {
            body.put("username", username);
            body.put("old_password_hash", sha256Hex(oldPassword));
            body.put("new_password_hash", sha256Hex(newPassword));
        } catch (Exception e) {
            tvStatus.setText("Lỗi tạo dữ liệu đổi mật khẩu");
            return;
        }

        tvStatus.setText("Đang đổi mật khẩu...");

        Request request = new Request.Builder()
                .url(getBaseUrl() + "/auth/change-password")
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
                            tvStatus.setText("Đổi mật khẩu thất bại: " + data.optString("error", "Lỗi"));
                            return;
                        }

                        tvStatus.setText("Đổi mật khẩu thành công");
                        Toast.makeText(ChangePasswordActivity.this, "Đổi mật khẩu thành công", Toast.LENGTH_SHORT).show();
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
