package com.example.smarthome;

import android.os.Bundle;
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import org.json.JSONObject;
import org.json.JSONArray;

import java.io.IOException;
import java.util.Locale;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

public class RfidCardActivity extends AppCompatActivity {

    private static final String PREFS_NAME = "smarthome_prefs";
    private static final String KEY_BASE_URL = "base_url";
    private static final String DEFAULT_BASE_URL = "http://10.0.2.2:5000";
    private static final MediaType JSON = MediaType.get("application/json; charset=utf-8");

    private final OkHttpClient httpClient = new OkHttpClient();

    private EditText etOldUid;
    private EditText etNewUid;
    private TextView tvCurrent;
    private TextView tvStatus;
    private TextView tvHistory;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_rfid_card);

        etOldUid = findViewById(R.id.etRfidOld);
        etNewUid = findViewById(R.id.etRfidNew);
        tvCurrent = findViewById(R.id.tvRfidCurrent);
        tvStatus = findViewById(R.id.tvRfidStatus);
        tvHistory = findViewById(R.id.tvRfidHistory);

        Button btnSave = findViewById(R.id.btnRfidSave);
        Button btnBack = findViewById(R.id.btnRfidBack);

        btnSave.setOnClickListener(v -> saveRfidCard());
        btnBack.setOnClickListener(v -> finish());

        loadCurrentRfidCard();
        loadRfidScanHistory();
    }

    private String normalizeUid(String input) {
        return (input == null ? "" : input.trim().toUpperCase(Locale.US))
                .replaceAll("[^0-9A-F]", "");
    }

    private void loadCurrentRfidCard() {
        Request request = new Request.Builder()
                .url(getBaseUrl() + "/rfid/card")
                .get()
                .build();

        httpClient.newCall(request).enqueue(new Callback() {
            @Override
            public void onFailure(Call call, IOException e) {
                runOnUiThread(() -> tvCurrent.setText("Lỗi tải thẻ hiện tại: " + e.getMessage()));
            }

            @Override
            public void onResponse(Call call, Response response) throws IOException {
                String responseBody = response.body() != null ? response.body().string() : "";
                runOnUiThread(() -> {
                    try {
                        JSONObject data = responseBody.isEmpty() ? new JSONObject() : new JSONObject(responseBody);
                        if (!response.isSuccessful() || !data.optBoolean("success", false)) {
                            tvCurrent.setText("Không tải được thẻ hiện tại");
                            return;
                        }

                        boolean initialized = data.optBoolean("is_initialized", false);
                        if (!initialized) {
                            tvCurrent.setText("Chưa khởi tạo thẻ RFID. Để trống mã cũ để tạo mới.");
                            return;
                        }

                        String uid = data.optString("uid", "");
                        String updatedAt = data.optString("updated_at", "--");
                        tvCurrent.setText("Mã hiện tại: " + uid + "\nCập nhật: " + updatedAt);
                    } catch (Exception e) {
                        tvCurrent.setText("Lỗi parse dữ liệu thẻ hiện tại");
                    }
                });
            }
        });
    }

    private void loadRfidScanHistory() {
        Request request = new Request.Builder()
                .url(getBaseUrl() + "/rfid/scans?limit=20")
                .get()
                .build();

        httpClient.newCall(request).enqueue(new Callback() {
            @Override
            public void onFailure(Call call, IOException e) {
                runOnUiThread(() -> tvHistory.setText("Lỗi tải lịch sử quét: " + e.getMessage()));
            }

            @Override
            public void onResponse(Call call, Response response) throws IOException {
                String responseBody = response.body() != null ? response.body().string() : "";
                runOnUiThread(() -> {
                    try {
                        JSONObject data = responseBody.isEmpty() ? new JSONObject() : new JSONObject(responseBody);
                        if (!response.isSuccessful() || !data.optBoolean("success", false)) {
                            tvHistory.setText("Không tải được lịch sử quét thẻ");
                            return;
                        }

                        JSONArray items = data.optJSONArray("items");
                        if (items == null || items.length() == 0) {
                            tvHistory.setText("Chưa có lịch sử quét RFID");
                            return;
                        }

                        StringBuilder builder = new StringBuilder();
                        for (int i = 0; i < items.length(); i++) {
                            JSONObject item = items.optJSONObject(i);
                            if (item == null) continue;

                            String timestamp = item.optString("timestamp", "--");
                            String uid = item.optString("uid", "--");
                            String status = item.optString("status", "--");

                            builder.append(i + 1)
                                    .append(". ")
                                    .append(timestamp)
                                    .append(" | UID: ")
                                    .append(uid)
                                    .append(" | ")
                                    .append(status)
                                    .append("\n");
                        }

                        tvHistory.setText(builder.toString().trim());
                    } catch (Exception e) {
                        tvHistory.setText("Lỗi parse lịch sử quét thẻ");
                    }
                });
            }
        });
    }

    private void saveRfidCard() {
        String oldUid = normalizeUid(etOldUid.getText().toString());
        String newUid = normalizeUid(etNewUid.getText().toString());

        if (newUid.isEmpty()) {
            tvStatus.setText("Vui lòng nhập mã thẻ mới");
            return;
        }

        JSONObject body = new JSONObject();
        try {
            body.put("old_uid", oldUid);
            body.put("new_uid", newUid);
        } catch (Exception e) {
            tvStatus.setText("Lỗi tạo dữ liệu gửi lên server");
            return;
        }

        tvStatus.setText("Đang lưu thẻ RFID...");

        Request request = new Request.Builder()
                .url(getBaseUrl() + "/rfid/card")
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
                        String uid = data.optString("uid", "");
                        if ("initialize".equals(mode)) {
                            tvStatus.setText("Khởi tạo thẻ thành công: " + uid);
                        } else {
                            tvStatus.setText("Đổi thẻ thành công: " + uid);
                        }

                        etOldUid.setText("");
                        etNewUid.setText("");
                        Toast.makeText(RfidCardActivity.this, "Lưu thẻ RFID thành công", Toast.LENGTH_SHORT).show();
                        loadCurrentRfidCard();
                        loadRfidScanHistory();
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
}
