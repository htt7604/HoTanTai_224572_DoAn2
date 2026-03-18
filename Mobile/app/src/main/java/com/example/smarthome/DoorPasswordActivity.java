package com.example.smarthome;

import android.os.Bundle;
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import org.json.JSONObject;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

public class DoorPasswordActivity extends AppCompatActivity {

    private static final String PREFS_NAME = "smarthome_prefs";
    private static final String KEY_BASE_URL = "base_url";
    private static final String DEFAULT_BASE_URL = "http://10.0.2.2:5000";
    private static final MediaType JSON = MediaType.get("application/json; charset=utf-8");

    private final OkHttpClient httpClient = new OkHttpClient();

    private EditText etOldPassword;
    private EditText etNewPassword;
    private TextView tvCurrent;
    private TextView tvStatus;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_door_password);

        etOldPassword = findViewById(R.id.etDoorPasswordOld);
        etNewPassword = findViewById(R.id.etDoorPasswordNew);
        tvCurrent = findViewById(R.id.tvDoorPasswordCurrent);
        tvStatus = findViewById(R.id.tvDoorPasswordStatus);

        Button btnSave = findViewById(R.id.btnDoorPasswordSave);
        Button btnBack = findViewById(R.id.btnDoorPasswordBack);

        btnSave.setOnClickListener(v -> saveDoorPassword());
        btnBack.setOnClickListener(v -> finish());

        loadDoorPasswordInfo();
    }

    private void loadDoorPasswordInfo() {
        Request request = new Request.Builder()
                .url(getBaseUrl() + "/door-password")
                .get()
                .build();

        httpClient.newCall(request).enqueue(new Callback() {
            @Override
            public void onFailure(Call call, IOException e) {
                runOnUiThread(() -> tvCurrent.setText("Lỗi tải trạng thái: " + e.getMessage()));
            }

            @Override
            public void onResponse(Call call, Response response) throws IOException {
                String responseBody = response.body() != null ? response.body().string() : "";
                runOnUiThread(() -> {
                    try {
                        JSONObject data = responseBody.isEmpty() ? new JSONObject() : new JSONObject(responseBody);
                        if (!response.isSuccessful() || !data.optBoolean("success", false)) {
                            tvCurrent.setText("Không tải được trạng thái mật khẩu cửa");
                            return;
                        }

                        boolean initialized = data.optBoolean("is_initialized", false);
                        if (!initialized) {
                            tvCurrent.setText("Chưa có mật khẩu mở cửa. Để trống mật khẩu cũ để khởi tạo.");
                            return;
                        }

                        String updatedAt = data.optString("updated_at", "--");
                        tvCurrent.setText("Đã có mật khẩu mở cửa\nCập nhật: " + updatedAt);
                    } catch (Exception e) {
                        tvCurrent.setText("Lỗi parse trạng thái mật khẩu cửa");
                    }
                });
            }
        });
    }

    private void saveDoorPassword() {
        String oldPassword = etOldPassword.getText().toString();
        String newPassword = etNewPassword.getText().toString();

        if (newPassword.trim().isEmpty()) {
            tvStatus.setText("Vui lòng nhập mật khẩu mới");
            return;
        }

        JSONObject body = new JSONObject();
        try {
            body.put("old_password_hash", oldPassword.trim().isEmpty() ? "" : sha256Hex(oldPassword));
            body.put("new_password_hash", sha256Hex(newPassword));
        } catch (Exception e) {
            tvStatus.setText("Lỗi tạo dữ liệu gửi lên server");
            return;
        }

        tvStatus.setText("Đang lưu mật khẩu cửa...");

        Request request = new Request.Builder()
                .url(getBaseUrl() + "/door-password")
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
                            tvStatus.setText("Lưu thất bại: " + data.optString("error", "Lỗi"));
                            return;
                        }

                        String mode = data.optString("mode", "change");
                        if ("initialize".equals(mode)) {
                            tvStatus.setText("Khởi tạo mật khẩu cửa thành công");
                        } else {
                            tvStatus.setText("Đổi mật khẩu cửa thành công");
                        }

                        etOldPassword.setText("");
                        etNewPassword.setText("");
                        Toast.makeText(DoorPasswordActivity.this, "Lưu mật khẩu cửa thành công", Toast.LENGTH_SHORT).show();
                        loadDoorPasswordInfo();
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

    private static String sha256Hex(String input) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest((input == null ? "" : input).getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder();
            for (byte b : hash) {
                sb.append(String.format("%02x", b));
            }
            return sb.toString();
        } catch (Exception e) {
            return "";
        }
    }
}
