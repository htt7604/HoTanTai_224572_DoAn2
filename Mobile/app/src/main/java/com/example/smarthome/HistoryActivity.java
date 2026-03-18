package com.example.smarthome;

import android.os.Bundle;
import android.text.InputType;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ArrayAdapter;
import android.widget.BaseAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ListView;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import androidx.activity.EdgeToEdge;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.IOException;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Locale;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;

public class HistoryActivity extends AppCompatActivity {

    private static final String PREFS_NAME = "smarthome_prefs";
    private static final String KEY_BASE_URL = "base_url";
    private static final String DEFAULT_BASE_URL = "http://103.166.182.44:5000";

    private final OkHttpClient httpClient = new OkHttpClient();
    private final List<SensorHistoryItem> historyItems = new ArrayList<>();

    private EditText etBaseUrlHistory;
    private Spinner spPeriod;
    private EditText etPeriodValue;
    private TextView tvHistorySummary;
    private TextView tvHistoryStatus;
    private HistoryAdapter historyAdapter;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        EdgeToEdge.enable(this);
        setContentView(R.layout.activity_history);

        bindViews();
        setupWindowInsets();
        setupPeriodSpinner();
        loadSavedBaseUrl();
        setupActions();

        updatePeriodInputUi();
        loadLatestHistory();
    }

    private void bindViews() {
        etBaseUrlHistory = findViewById(R.id.etBaseUrlHistory);
        spPeriod = findViewById(R.id.spPeriod);
        etPeriodValue = findViewById(R.id.etPeriodValue);
        tvHistorySummary = findViewById(R.id.tvHistorySummary);
        tvHistoryStatus = findViewById(R.id.tvHistoryStatus);

        ListView lvHistory = findViewById(R.id.lvHistory);
        historyAdapter = new HistoryAdapter();
        lvHistory.setAdapter(historyAdapter);
    }

    private void setupWindowInsets() {
        ViewCompat.setOnApplyWindowInsetsListener(findViewById(R.id.historyRoot), (v, insets) -> {
            Insets systemBars = insets.getInsets(WindowInsetsCompat.Type.systemBars());
            v.setPadding(systemBars.left, systemBars.top, systemBars.right, systemBars.bottom);
            return insets;
        });
    }

    private void setupPeriodSpinner() {
        String[] options = new String[]{"Giờ", "Ngày", "Tháng", "Năm"};
        ArrayAdapter<String> adapter = new ArrayAdapter<>(this, android.R.layout.simple_spinner_item, options);
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        spPeriod.setAdapter(adapter);
        spPeriod.setSelection(1);
    }

    private void setupActions() {
        Button btnBackMain = findViewById(R.id.btnBackMain);
        Button btnApplyFilter = findViewById(R.id.btnApplyFilter);
        Button btnLoadLatest = findViewById(R.id.btnLoadLatest);

        btnBackMain.setOnClickListener(v -> finish());

        btnApplyFilter.setOnClickListener(v -> loadFilteredHistory());

        btnLoadLatest.setOnClickListener(v -> loadLatestHistory());

        spPeriod.setOnItemSelectedListener(new android.widget.AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(android.widget.AdapterView<?> parent, View view, int position, long id) {
                updatePeriodInputUi();
            }

            @Override
            public void onNothingSelected(android.widget.AdapterView<?> parent) {
            }
        });
    }

    private void loadSavedBaseUrl() {
        String baseUrl = getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
                .getString(KEY_BASE_URL, DEFAULT_BASE_URL);
        etBaseUrlHistory.setText(baseUrl);
    }

    private String sanitizeBaseUrl(String value) {
        String trimmed = value == null ? "" : value.trim();
        if (trimmed.endsWith("/")) {
            trimmed = trimmed.substring(0, trimmed.length() - 1);
        }
        if (trimmed.isEmpty()) {
            return DEFAULT_BASE_URL;
        }
        return trimmed;
    }

    private String getBaseUrl() {
        return sanitizeBaseUrl(etBaseUrlHistory.getText().toString());
    }

    private void updatePeriodInputUi() {
        String period = getSelectedPeriod();

        if ("hour".equals(period)) {
            etPeriodValue.setInputType(InputType.TYPE_CLASS_TEXT);
            etPeriodValue.setHint("YYYY-MM-DDTHH (VD: 2026-03-15T14)");
            etPeriodValue.setText(nowHourValue());
            return;
        }

        if ("day".equals(period)) {
            etPeriodValue.setInputType(InputType.TYPE_CLASS_DATETIME);
            etPeriodValue.setHint("YYYY-MM-DD (VD: 2026-03-15)");
            etPeriodValue.setText(nowDayValue());
            return;
        }

        if ("month".equals(period)) {
            etPeriodValue.setInputType(InputType.TYPE_CLASS_DATETIME);
            etPeriodValue.setHint("YYYY-MM (VD: 2026-03)");
            etPeriodValue.setText(nowMonthValue());
            return;
        }

        etPeriodValue.setInputType(InputType.TYPE_CLASS_NUMBER);
        etPeriodValue.setHint("YYYY (VD: 2026)");
        etPeriodValue.setText(nowYearValue());
    }

    private String nowHourValue() {
        return new SimpleDateFormat("yyyy-MM-dd'T'HH", Locale.US).format(new Date());
    }

    private String nowDayValue() {
        return new SimpleDateFormat("yyyy-MM-dd", Locale.US).format(new Date());
    }

    private String nowMonthValue() {
        return new SimpleDateFormat("yyyy-MM", Locale.US).format(new Date());
    }

    private String nowYearValue() {
        return new SimpleDateFormat("yyyy", Locale.US).format(new Date());
    }

    private String getSelectedPeriod() {
        int pos = spPeriod.getSelectedItemPosition();
        if (pos == 0) {
            return "hour";
        }
        if (pos == 1) {
            return "day";
        }
        if (pos == 2) {
            return "month";
        }
        return "year";
    }

    private void loadLatestHistory() {
        setStatus("Đang tải dữ liệu mới nhất...");
        String url = getBaseUrl() + "/sensor/history?limit=200";
        fetchHistory(url, "Hiển thị bản ghi mới nhất");
    }

    private void loadFilteredHistory() {
        String period = getSelectedPeriod();
        String value = etPeriodValue.getText().toString().trim();

        if (value.isEmpty()) {
            setStatus("Vui lòng nhập giá trị thời gian để lọc");
            return;
        }

        setStatus("Đang lọc dữ liệu...");
        String url = getBaseUrl()
                + "/sensor/history?period=" + period
                + "&value=" + value
                + "&limit=2000";

        fetchHistory(url, "Bộ lọc " + period + " = " + value);
    }

    private void fetchHistory(String url, String summaryPrefix) {
        Request request = new Request.Builder()
                .url(url)
                .get()
                .build();

        httpClient.newCall(request).enqueue(new Callback() {
            @Override
            public void onFailure(Call call, IOException e) {
                runOnUiThread(() -> {
                    setStatus("Lỗi kết nối: " + e.getMessage());
                    Toast.makeText(HistoryActivity.this,
                            "Không kết nối được server. Hãy kiểm tra Base URL.",
                            Toast.LENGTH_LONG).show();
                });
            }

            @Override
            public void onResponse(Call call, Response response) throws IOException {
                String body = response.body() != null ? response.body().string() : "";
                if (!response.isSuccessful()) {
                    runOnUiThread(() -> setStatus("Server lỗi " + response.code()));
                    return;
                }

                try {
                    JSONObject result = new JSONObject(body);
                    boolean success = result.optBoolean("success", false);
                    if (!success) {
                        runOnUiThread(() -> setStatus("API trả về thất bại"));
                        return;
                    }

                    JSONArray data = result.optJSONArray("data");
                    ArrayList<SensorHistoryItem> rows = new ArrayList<>();
                    if (data != null) {
                        for (int i = 0; i < data.length(); i++) {
                            JSONObject item = data.optJSONObject(i);
                            if (item == null) {
                                continue;
                            }

                            rows.add(new SensorHistoryItem(
                                    item.optString("timestamp", "--"),
                                    item.optDouble("temp", Double.NaN),
                                    item.optDouble("hum", Double.NaN),
                                    item.optInt("gas", 0)
                            ));
                        }
                    }

                    int count = result.optInt("count", rows.size());
                    runOnUiThread(() -> {
                        historyItems.clear();
                        historyItems.addAll(rows);
                        historyAdapter.notifyDataSetChanged();
                        tvHistorySummary.setText(summaryPrefix + ": " + count + " bản ghi.");
                        setStatus("Đã tải dữ liệu lịch sử");
                    });
                } catch (Exception e) {
                    runOnUiThread(() -> setStatus("Lỗi parse dữ liệu: " + e.getMessage()));
                }
            }
        });
    }

    private String formatDecimal(double value) {
        if (Double.isNaN(value)) {
            return "--";
        }
        return String.format(Locale.US, "%.1f", value);
    }

    private String formatTimestamp(String input) {
        if (input == null || input.trim().isEmpty()) {
            return "--";
        }
        return input.replace("T", " ");
    }

    private void setStatus(String message) {
        tvHistoryStatus.setText("Status: " + message);
    }

    private static class SensorHistoryItem {
        final String timestamp;
        final double temp;
        final double hum;
        final int gas;

        SensorHistoryItem(String timestamp, double temp, double hum, int gas) {
            this.timestamp = timestamp;
            this.temp = temp;
            this.hum = hum;
            this.gas = gas;
        }
    }

    private class HistoryAdapter extends BaseAdapter {

        @Override
        public int getCount() {
            return historyItems.size();
        }

        @Override
        public Object getItem(int position) {
            return historyItems.get(position);
        }

        @Override
        public long getItemId(int position) {
            return position;
        }

        @Override
        public View getView(int position, View convertView, ViewGroup parent) {
            View view = convertView;
            if (view == null) {
                view = LayoutInflater.from(HistoryActivity.this)
                        .inflate(R.layout.item_history_sensor, parent, false);
            }

            TextView tvRowTime = view.findViewById(R.id.tvRowTime);
            TextView tvRowTemp = view.findViewById(R.id.tvRowTemp);
            TextView tvRowHum = view.findViewById(R.id.tvRowHum);
            TextView tvRowGas = view.findViewById(R.id.tvRowGas);

            SensorHistoryItem item = historyItems.get(position);
            tvRowTime.setText(formatTimestamp(item.timestamp));
            tvRowTemp.setText(formatDecimal(item.temp));
            tvRowHum.setText(formatDecimal(item.hum));
            tvRowGas.setText(String.valueOf(item.gas));
            return view;
        }
    }
}
