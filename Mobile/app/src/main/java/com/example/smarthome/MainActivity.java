package com.example.smarthome;

import android.Manifest;
import android.animation.ObjectAnimator;
import android.app.Activity;
import android.app.AlertDialog;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;
import android.speech.RecognizerIntent;
import android.speech.tts.TextToSpeech;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ImageButton;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;
import android.widget.ArrayAdapter;

import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;

import androidx.activity.EdgeToEdge;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.NotificationCompat;
import androidx.core.app.NotificationManagerCompat;
import androidx.core.content.ContextCompat;
import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;

import com.google.firebase.messaging.FirebaseMessaging;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.IOException;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.HashMap;
import java.util.Map;
import java.util.Locale;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

public class MainActivity extends AppCompatActivity {

    private static final String PREFS_NAME = "smarthome_prefs";
    private static final String KEY_BASE_URL = "base_url";
    private static final String DEFAULT_BASE_URL = "http://127.0.0.1:5000";
    private static final String KEY_DEVICE_NAMES_JSON = "device_names_json";
    private static final String DOOR_PASSWORD = "123456A";
    private static final long POLLING_INTERVAL_MS = 2000L;
    private static final MediaType JSON = MediaType.get("application/json; charset=utf-8");
        private static final int GAS_DANGER_THRESHOLD = 1200;
        private static final String ALERT_CHANNEL_ID = "smarthome_alerts";
        private static final int FIRE_NOTIFICATION_ID = 1001;
        private static final int GAS_NOTIFICATION_ID = 1002;
        private static final long DANGER_RENOTIFY_MS = 60_000L;
        private static final long NETWORK_ERROR_THROTTLE_MS = 8_000L;
        private static final String[] DEVICE_KEYS = {
            "door", "fan", "roof", "light1", "light2", "light3", "light4"
    };

    private final OkHttpClient httpClient = new OkHttpClient();
    private final Handler pollingHandler = new Handler(Looper.getMainLooper());
    private final Map<String, String> deviceNameMap = new HashMap<>();
    private static final int LIGHT_ON_ICON_COLOR = 0xFFFFC107;
    private static final int LIGHT_OFF_ICON_COLOR = 0xFF9E9E9E;
    private static final int LIGHT_ON_CARD_BG = 0xFFFFF8E1;
    private static final int LIGHT_OFF_CARD_BG = 0xFFFFFFFF;
    private static final int LIGHT_ON_TEXT_COLOR = 0xFFFB8C00;
    private static final int LIGHT_OFF_TEXT_COLOR = 0xFF6E7B91;

    private TextToSpeech textToSpeech;
    private boolean isVoiceListening = false;
    private Button btnVoiceOnce;
    private ActivityResultLauncher<Intent> speechToTextLauncher;
    private ActivityResultLauncher<String> requestMicPermissionLauncher;
    private ActivityResultLauncher<String> requestNotificationPermissionLauncher;
    private boolean wasFlameDanger = false;
    private boolean wasGasDanger = false;
    private long lastDangerNotifyAtMs = 0L;
    private long lastNetworkErrorAtMs = 0L;
    private boolean networkDisconnectedState = false;

    private final Runnable pollSensorTask = new Runnable() {
        @Override
        public void run() {
            fetchLatestSensor();
            pollingHandler.postDelayed(this, POLLING_INTERVAL_MS);
        }
    };

    private EditText etBaseUrl;
    private EditText etDoorPassword;
    private EditText etDeviceName;
    private Spinner spDeviceKey;

    private TextView tvStatus;
    private TextView tvConnectionStatus;
    private TextView tvTempValue;
    private TextView tvHumValue;
    private TextView tvGasValue;
    private TextView tvRainValue;
    private TextView tvFlameValue;
    private TextView tvPirValue;
    private TextView tvDoorValue;
    private TextView tvFanValue;
    private TextView tvLastUpdate;
    private TextView tvVoiceStatus;
    private TextView tvDeviceNameStatus;
    private TextView tvStatusDoorTitle;
    private TextView tvStatusFanTitle;
    private TextView tvDoorPanelTitle;
    private TextView tvDoorPasswordLabel;
    private TextView tvFanControlLabel;
    private TextView tvRoofControlLabel;
    private TextView tvLight1Name;
    private TextView tvLight2Name;
    private TextView tvLight3Name;
    private TextView tvLight4Name;
    private TextView tvLight1State;
    private TextView tvLight2State;
    private TextView tvLight3State;
    private TextView tvLight4State;

    private android.view.View cardLight1;
    private android.view.View cardLight2;
    private android.view.View cardLight3;
    private android.view.View cardLight4;
    private ImageButton btnLight1;
    private ImageButton btnLight2;
    private ImageButton btnLight3;
    private ImageButton btnLight4;

    private boolean light1On = false;
    private boolean light2On = false;
    private boolean light3On = false;
    private boolean light4On = false;
    private boolean hasInitializedLightState = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        EdgeToEdge.enable(this);
        setContentView(R.layout.activity_main);

        bindViews();
        initVoiceLaunchers();
        createAlertNotificationChannel();
        requestNotificationPermissionIfNeeded();
        setupWindowInsets();
        setupActions();
        setupDeviceSpinner();
        initTextToSpeech();
        loadSavedBaseUrl();
        registerPushTokenIfPossible();
        loadCachedDeviceNames();
        applyDeviceNamesToUi();
        loadDeviceNames();
        fetchLatestSensor();
        startPolling();
    }

    private void initVoiceLaunchers() {
        speechToTextLauncher = registerForActivityResult(
                new ActivityResultContracts.StartActivityForResult(),
                result -> {
                    if (result.getResultCode() != Activity.RESULT_OK || result.getData() == null) {
                        isVoiceListening = false;
                        if (btnVoiceOnce != null) {
                            btnVoiceOnce.setEnabled(true);
                        }
                        tvVoiceStatus.setText("Không nhận được giọng nói.");
                        return;
                    }

                    ArrayList<String> results = result.getData().getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS);
                    if (results == null || results.isEmpty()) {
                        isVoiceListening = false;
                        if (btnVoiceOnce != null) {
                            btnVoiceOnce.setEnabled(true);
                        }
                        tvVoiceStatus.setText("Không nhận diện được giọng nói.");
                        return;
                    }

                    String spokenText = results.get(0);
                    tvVoiceStatus.setText("Bạn nói: " + spokenText);
                    processVoiceTextOnServer(spokenText);
                }
        );

        requestMicPermissionLauncher = registerForActivityResult(
                new ActivityResultContracts.RequestPermission(),
                isGranted -> {
                    if (isGranted) {
                        launchSpeechRecognizer();
                    } else {
                        isVoiceListening = false;
                        if (btnVoiceOnce != null) {
                            btnVoiceOnce.setEnabled(true);
                        }
                        tvVoiceStatus.setText("Bạn chưa cấp quyền micro.");
                        showError("Cần cấp quyền micro để dùng giọng nói");
                    }
                }
        );

        requestNotificationPermissionLauncher = registerForActivityResult(
                new ActivityResultContracts.RequestPermission(),
                isGranted -> {
                    if (!isGranted) {
                        Toast.makeText(this,
                                "Bạn chưa cấp quyền thông báo, cảnh báo nổi sẽ không hiển thị.",
                                Toast.LENGTH_LONG).show();
                    }
                }
        );
    }

    private void createAlertNotificationChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) {
            return;
        }

        NotificationChannel channel = new NotificationChannel(
                ALERT_CHANNEL_ID,
                "Cảnh báo nguy hiểm",
                NotificationManager.IMPORTANCE_HIGH
        );
        channel.setDescription("Thông báo nổi khi phát hiện lửa hoặc nồng độ gas nguy hiểm");
        NotificationManager manager = getSystemService(NotificationManager.class);
        if (manager != null) {
            manager.createNotificationChannel(channel);
        }
    }

    private void requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) {
            return;
        }
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
                == PackageManager.PERMISSION_GRANTED) {
            return;
        }
        requestNotificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS);
    }

    private void setupWindowInsets() {
        ViewCompat.setOnApplyWindowInsetsListener(findViewById(R.id.main), (v, insets) -> {
            Insets systemBars = insets.getInsets(WindowInsetsCompat.Type.systemBars());
            v.setPadding(systemBars.left, systemBars.top, systemBars.right, systemBars.bottom);
            return insets;
        });
    }

    private void bindViews() {
        etBaseUrl = findViewById(R.id.etBaseUrl);
        etDoorPassword = findViewById(R.id.etDoorPassword);
        etDeviceName = findViewById(R.id.etDeviceName);
        spDeviceKey = findViewById(R.id.spDeviceKey);

        tvStatus = findViewById(R.id.tvStatus);
        tvConnectionStatus = findViewById(R.id.tvConnectionStatus);
        tvTempValue = findViewById(R.id.tvTempValue);
        tvHumValue = findViewById(R.id.tvHumValue);
        tvGasValue = findViewById(R.id.tvGasValue);
        tvRainValue = findViewById(R.id.tvRainValue);
        tvFlameValue = findViewById(R.id.tvFlameValue);
        tvPirValue = findViewById(R.id.tvPirValue);
        tvDoorValue = findViewById(R.id.tvDoorValue);
        tvFanValue = findViewById(R.id.tvFanValue);
        tvLastUpdate = findViewById(R.id.tvLastUpdate);
        tvVoiceStatus = findViewById(R.id.tvVoiceStatus);
        tvDeviceNameStatus = findViewById(R.id.tvDeviceNameStatus);
        tvStatusDoorTitle = findViewById(R.id.tvStatusDoorTitle);
        tvStatusFanTitle = findViewById(R.id.tvStatusFanTitle);
        tvDoorPanelTitle = findViewById(R.id.tvDoorPanelTitle);
        tvDoorPasswordLabel = findViewById(R.id.tvDoorPasswordLabel);
        tvFanControlLabel = findViewById(R.id.tvFanControlLabel);
        tvRoofControlLabel = findViewById(R.id.tvRoofControlLabel);

        tvLight1Name = findViewById(R.id.tvLight1Name);
        tvLight2Name = findViewById(R.id.tvLight2Name);
        tvLight3Name = findViewById(R.id.tvLight3Name);
        tvLight4Name = findViewById(R.id.tvLight4Name);
        tvLight1State = findViewById(R.id.tvLight1State);
        tvLight2State = findViewById(R.id.tvLight2State);
        tvLight3State = findViewById(R.id.tvLight3State);
        tvLight4State = findViewById(R.id.tvLight4State);

        cardLight1 = findViewById(R.id.cardLight1);
        cardLight2 = findViewById(R.id.cardLight2);
        cardLight3 = findViewById(R.id.cardLight3);
        cardLight4 = findViewById(R.id.cardLight4);
        btnLight1 = findViewById(R.id.btnLight1);
        btnLight2 = findViewById(R.id.btnLight2);
        btnLight3 = findViewById(R.id.btnLight3);
        btnLight4 = findViewById(R.id.btnLight4);
    }

    private void setupActions() {
        Button btnSaveBaseUrl = findViewById(R.id.btnSaveBaseUrl);
        Button btnDoorOpen = findViewById(R.id.btnDoorOpen);
        Button btnDoorClose = findViewById(R.id.btnDoorClose);
        Button btnFanOn = findViewById(R.id.btnFanOn);
        Button btnFanOff = findViewById(R.id.btnFanOff);
        Button btnRoofOpen = findViewById(R.id.btnRoofOpen);
        Button btnRoofClose = findViewById(R.id.btnRoofClose);
        btnVoiceOnce = findViewById(R.id.btnVoiceOnce);
        Button btnSaveDeviceName = findViewById(R.id.btnSaveDeviceName);
        Button btnRefresh = findViewById(R.id.btnRefresh);

        btnSaveBaseUrl.setOnClickListener(v -> {
            saveBaseUrl();
            registerPushTokenIfPossible();
            fetchLatestSensor();
        });

        btnDoorOpen.setOnClickListener(v -> openDoorWithPassword());
        btnDoorClose.setOnClickListener(v -> controlDoor("CLOSE"));
        btnFanOn.setOnClickListener(v -> controlFan(true));
        btnFanOff.setOnClickListener(v -> controlFan(false));
        btnRoofOpen.setOnClickListener(v -> controlRoof(true));
        btnRoofClose.setOnClickListener(v -> controlRoof(false));
        btnVoiceOnce.setOnClickListener(v -> voiceOnce());
        btnSaveDeviceName.setOnClickListener(v -> saveDeviceName());
        btnRefresh.setOnClickListener(v -> fetchLatestSensor());
        btnLight1.setOnClickListener(v -> onLightCardTapped(1));
        btnLight2.setOnClickListener(v -> onLightCardTapped(2));
        btnLight3.setOnClickListener(v -> onLightCardTapped(3));
        btnLight4.setOnClickListener(v -> onLightCardTapped(4));

        spDeviceKey.setOnItemSelectedListener(new android.widget.AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(android.widget.AdapterView<?> parent, android.view.View view, int position, long id) {
                applySelectedDeviceName();
            }

            @Override
            public void onNothingSelected(android.widget.AdapterView<?> parent) {
            }
        });

    }

    private void setupDeviceSpinner() {
        String[] names = new String[DEVICE_KEYS.length];
        for (int i = 0; i < DEVICE_KEYS.length; i++) {
            names[i] = getDeviceDisplayName(DEVICE_KEYS[i], fallbackName(DEVICE_KEYS[i]));
        }
        ArrayAdapter<String> adapter = new ArrayAdapter<>(this, android.R.layout.simple_spinner_item, names);
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        spDeviceKey.setAdapter(adapter);
    }

    private void loadSavedBaseUrl() {
        String baseUrl = getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
                .getString(KEY_BASE_URL, DEFAULT_BASE_URL);
        etBaseUrl.setText(baseUrl);
    }

    private void saveBaseUrl() {
        String baseUrl = sanitizeBaseUrl(etBaseUrl.getText().toString());
        etBaseUrl.setText(baseUrl);
        getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
                .edit()
                .putString(KEY_BASE_URL, baseUrl)
                .apply();
        setStatus("Saved server: " + baseUrl);
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
        return sanitizeBaseUrl(etBaseUrl.getText().toString());
    }

    private String getConnectionHint() {
        String baseUrl = getBaseUrl().toLowerCase(Locale.US);
        if (baseUrl.contains("127.0.0.1") || baseUrl.contains("localhost")) {
            return " Bạn đang dùng localhost/127.0.0.1. Trên điện thoại thật, hãy đổi Base URL thành IP LAN của máy chạy server (ví dụ: http://192.168.2.84:5000).";
        }
        return "";
    }

    private void registerPushTokenIfPossible() {
        try {
            FirebaseMessaging.getInstance().getToken()
                    .addOnCompleteListener(task -> {
                        if (!task.isSuccessful()) {
                            return;
                        }
                        String token = task.getResult();
                        PushTokenRegistrar.register(getApplicationContext(), token);
                    });
        } catch (Exception ignored) {
        }
    }

    private void openDoorWithPassword() {
        String password = etDoorPassword.getText().toString().trim();
        if (!DOOR_PASSWORD.equals(password)) {
            showError("Mật khẩu sai! Mật khẩu đúng là: " + DOOR_PASSWORD);
            return;
        }
        controlDoor("OPEN");
    }

    private void controlDoor(String action) {
        try {
            JSONObject body = new JSONObject();
            body.put("action", action);
            postJson("/control/door", body,
                    "OPEN".equals(action) ? "Mở cửa thành công" : "Đóng cửa thành công");
            if ("OPEN".equals(action)) {
                etDoorPassword.setText("");
            }
        } catch (Exception e) {
            showError("Cannot build door request: " + e.getMessage());
        }
    }

    private void controlLight(int lightNum, boolean state) {
        try {
            JSONObject body = new JSONObject();
            body.put("light", lightNum);
            body.put("state", state);
            postJson("/control/light", body,
                    (state ? "Bật " : "Tắt ") + getDeviceDisplayName("light" + lightNum, "đèn " + lightNum));
        } catch (Exception e) {
            showError("Cannot build light request: " + e.getMessage());
        }
    }

    private void onLightCardTapped(int lightNum) {
        boolean nextState;
        if (lightNum == 1) {
            nextState = !light1On;
            light1On = nextState;
            updateLightCard(cardLight1, btnLight1, tvLight1State, light1On, true);
        } else if (lightNum == 2) {
            nextState = !light2On;
            light2On = nextState;
            updateLightCard(cardLight2, btnLight2, tvLight2State, light2On, true);
        } else if (lightNum == 3) {
            nextState = !light3On;
            light3On = nextState;
            updateLightCard(cardLight3, btnLight3, tvLight3State, light3On, true);
        } else if (lightNum == 4) {
            nextState = !light4On;
            light4On = nextState;
            updateLightCard(cardLight4, btnLight4, tvLight4State, light4On, true);
        } else {
            return;
        }

        controlLight(lightNum, nextState);
    }

    private void controlFan(boolean state) {
        try {
            JSONObject body = new JSONObject();
            body.put("state", state);
            postJson("/control/fan", body,
                    (state ? "Bật " : "Tắt ") + getDeviceDisplayName("fan", "quạt"));
        } catch (Exception e) {
            showError("Cannot build fan request: " + e.getMessage());
        }
    }

    private void controlRoof(boolean state) {
        try {
            JSONObject body = new JSONObject();
            body.put("state", state);
            postJson("/control/roof", body,
                    (state ? "Mở " : "Đóng ") + getDeviceDisplayName("roof", "mái che"));
        } catch (Exception e) {
            showError("Cannot build roof request: " + e.getMessage());
        }
    }

    private void voiceOnce() {
        if (isVoiceListening) {
            return;
        }

        isVoiceListening = true;
        tvVoiceStatus.setText("Đang nghe trên điện thoại...");
        if (btnVoiceOnce != null) {
            btnVoiceOnce.setEnabled(false);
        }

        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
                != PackageManager.PERMISSION_GRANTED) {
            requestMicPermissionLauncher.launch(Manifest.permission.RECORD_AUDIO);
            return;
        }

        launchSpeechRecognizer();
    }

    private void launchSpeechRecognizer() {
        Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "vi-VN");
        intent.putExtra(RecognizerIntent.EXTRA_PROMPT, "Mời bạn nói lệnh điều khiển nhà thông minh");

        try {
            speechToTextLauncher.launch(intent);
        } catch (Exception e) {
            isVoiceListening = false;
            if (btnVoiceOnce != null) {
                btnVoiceOnce.setEnabled(true);
            }
            tvVoiceStatus.setText("Thiết bị không hỗ trợ nhận dạng giọng nói.");
            showError("Không mở được nhận dạng giọng nói: " + e.getMessage());
        }
    }

    private void processVoiceTextOnServer(String spokenText) {
        try {
            JSONObject body = new JSONObject();
            body.put("text", spokenText);

            Request request = new Request.Builder()
                    .url(getBaseUrl() + "/ai/process")
                    .post(RequestBody.create(body.toString(), JSON))
                    .build();

            httpClient.newCall(request).enqueue(new Callback() {
                @Override
                public void onFailure(Call call, IOException e) {
                    runOnUiThread(() -> {
                        isVoiceListening = false;
                        if (btnVoiceOnce != null) {
                            btnVoiceOnce.setEnabled(true);
                        }
                        tvVoiceStatus.setText("Lỗi gửi text lên server: " + e.getMessage() + getConnectionHint());
                    });
                }

                @Override
                public void onResponse(Call call, Response response) throws IOException {
                    String responseBody = response.body() != null ? response.body().string() : "";
                    runOnUiThread(() -> {
                        isVoiceListening = false;
                        if (btnVoiceOnce != null) {
                            btnVoiceOnce.setEnabled(true);
                        }

                        try {
                            JSONObject data = responseBody.isEmpty() ? new JSONObject() : new JSONObject(responseBody);
                            String replyText = data.optString("response_text", "").trim();
                            if (data.optBoolean("success", false)) {
                                String command = data.optString("command", "");
                                tvVoiceStatus.setText("Đã gửi lệnh: " + command);
                                if (!replyText.isEmpty()) {
                                    speakOnClient(replyText);
                                }
                                fetchLatestSensor();
                            } else {
                                String message = data.optString("message", "Không nhận diện được lệnh");
                                tvVoiceStatus.setText(message);
                                if (!replyText.isEmpty()) {
                                    speakOnClient(replyText);
                                }
                            }
                        } catch (Exception e) {
                            tvVoiceStatus.setText("Lỗi parse phản hồi server");
                        }
                    });
                }
            });
        } catch (Exception e) {
            isVoiceListening = false;
            if (btnVoiceOnce != null) {
                btnVoiceOnce.setEnabled(true);
            }
            showError("Không thể tạo request giọng nói: " + e.getMessage());
        }
    }

    private void initTextToSpeech() {
        textToSpeech = new TextToSpeech(this, status -> {
            if (status == TextToSpeech.SUCCESS) {
                textToSpeech.setLanguage(new Locale("vi", "VN"));
            }
        });
    }

    private void speakOnClient(String text) {
        if (textToSpeech == null || text == null || text.trim().isEmpty()) {
            return;
        }
        textToSpeech.speak(text, TextToSpeech.QUEUE_FLUSH, null, "smarthome_voice_reply");
    }

    private void fetchLatestSensor() {
        Request request = new Request.Builder()
                .url(getBaseUrl() + "/sensor/latest")
                .get()
                .build();

        setStatus("Đang tải dữ liệu cảm biến...");

        httpClient.newCall(request).enqueue(new Callback() {
            @Override
            public void onFailure(Call call, IOException e) {
                showNetworkErrorThrottled("Cannot reach server: " + e.getMessage() + getConnectionHint());
            }

            @Override
            public void onResponse(Call call, Response response) throws IOException {
                String responseBody = response.body() != null ? response.body().string() : "";
                if (!response.isSuccessful()) {
                    showError("Server error " + response.code() + ": " + responseBody);
                    return;
                }

                try {
                    JSONObject data = new JSONObject(responseBody);
                    runOnUiThread(() -> {
                        networkDisconnectedState = false;
                        updateConnectionUi(!data.has("message"));
                        applySensorToUi(data);
                        setStatus("Đã cập nhật dữ liệu cảm biến");
                    });
                } catch (Exception e) {
                    showNetworkErrorThrottled("Bad sensor data: " + e.getMessage());
                }
            }
        });
    }

    private void showNetworkErrorThrottled(String message) {
        long nowMs = System.currentTimeMillis();
        if (networkDisconnectedState && (nowMs - lastNetworkErrorAtMs) < NETWORK_ERROR_THROTTLE_MS) {
            return;
        }
        networkDisconnectedState = true;
        lastNetworkErrorAtMs = nowMs;
        showError(message);
    }

    private void applySensorToUi(JSONObject data) {
        applyDeviceNamesFromSensorResponse(data);

        if (data.has("message")) {
            setStatus("Chưa có dữ liệu từ ESP32");
            return;
        }

        boolean oldLight1On = light1On;
        boolean oldLight2On = light2On;
        boolean oldLight3On = light3On;
        boolean oldLight4On = light4On;

        light1On = data.optBoolean("light1", false);
        light2On = data.optBoolean("light2", false);
        light3On = data.optBoolean("light3", false);
        light4On = data.optBoolean("light4", false);

        boolean animateLight1 = hasInitializedLightState && oldLight1On != light1On;
        boolean animateLight2 = hasInitializedLightState && oldLight2On != light2On;
        boolean animateLight3 = hasInitializedLightState && oldLight3On != light3On;
        boolean animateLight4 = hasInitializedLightState && oldLight4On != light4On;
        updateLightCards(animateLight1, animateLight2, animateLight3, animateLight4);
        hasInitializedLightState = true;

        tvTempValue.setText(formatOneDecimal(data.optDouble("temp", 0.0)) + "°C");
        tvHumValue.setText(formatOneDecimal(data.optDouble("hum", 0.0)) + "%");
        tvGasValue.setText(String.valueOf(data.optInt("gas", 0)));

        boolean isRain = data.optBoolean("rain", false);
        boolean isFlame = data.optBoolean("flame", false);
        boolean isPir = data.optBoolean("pir", false);
        int gasValue = data.optInt("gas", 0);
        boolean isDoorOpen = isDoorOpenState(data.opt("door"));
        boolean isFanOn = data.optBoolean("fan", false);

        handleDangerAlerts(isFlame, gasValue);

        tvRainValue.setText(isRain ? "Có mưa" : "Không mưa");
        tvFlameValue.setText(isFlame ? "CÓ LỬA!" : "An toàn");
        tvPirValue.setText(isPir ? "Phát hiện" : "Không có");
        tvDoorValue.setText(isDoorOpen ? "MỞ" : "ĐÓNG");
        tvFanValue.setText(isFanOn ? "BẬT" : "TẮT");

        setAlertColor(tvRainValue, isRain);
        setAlertColor(tvFlameValue, isFlame);
        setAlertColor(tvPirValue, isPir);
        setAlertColor(tvDoorValue, isDoorOpen);
        setAlertColor(tvFanValue, isFanOn);

        String timestamp = data.optString("timestamp", "");
        if (!timestamp.isEmpty()) {
            tvLastUpdate.setText("Cập nhật lần cuối: " + formatTimestamp(timestamp));
        }
    }

    private void updateLightCards(boolean animateLight1, boolean animateLight2, boolean animateLight3, boolean animateLight4) {
        updateLightCard(cardLight1, btnLight1, tvLight1State, light1On, animateLight1);
        updateLightCard(cardLight2, btnLight2, tvLight2State, light2On, animateLight2);
        updateLightCard(cardLight3, btnLight3, tvLight3State, light3On, animateLight3);
        updateLightCard(cardLight4, btnLight4, tvLight4State, light4On, animateLight4);
    }

    private void handleDangerAlerts(boolean isFlameDangerNow, int gasValueNow) {
        boolean isGasDangerNow = gasValueNow > GAS_DANGER_THRESHOLD;
        long nowMs = System.currentTimeMillis();
        boolean canRenotify = (nowMs - lastDangerNotifyAtMs) >= DANGER_RENOTIFY_MS;

        if (isFlameDangerNow && (!wasFlameDanger || canRenotify)) {
            showDangerNotification(
                    FIRE_NOTIFICATION_ID,
                    "🚨 CẢNH BÁO CHÁY",
                    "Phát hiện lửa trong nhà. Hãy kiểm tra ngay!"
            );
            showDangerPopup("🚨 CẢNH BÁO CHÁY", "Phát hiện lửa trong nhà. Hãy kiểm tra ngay!");
            lastDangerNotifyAtMs = nowMs;
        }

        if (isGasDangerNow && (!wasGasDanger || canRenotify)) {
            showDangerNotification(
                    GAS_NOTIFICATION_ID,
                    "⚠️ CẢNH BÁO GAS",
                    "Nồng độ gas nguy hiểm: " + gasValueNow + ". Hãy xử lý ngay!"
            );
            showDangerPopup("⚠️ CẢNH BÁO GAS", "Nồng độ gas nguy hiểm: " + gasValueNow + ". Hãy xử lý ngay!");
            lastDangerNotifyAtMs = nowMs;
        }

        wasFlameDanger = isFlameDangerNow;
        wasGasDanger = isGasDangerNow;
    }

    private void showDangerPopup(String title, String message) {
        runOnUiThread(() -> {
            if (isFinishing() || isDestroyed()) {
                return;
            }
            new AlertDialog.Builder(MainActivity.this)
                    .setTitle(title)
                    .setMessage(message)
                    .setCancelable(true)
                    .setPositiveButton("Đã hiểu", (dialog, which) -> dialog.dismiss())
                    .show();
        });
    }

    private void showDangerNotification(int notificationId, String title, String message) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU
                && ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
                != PackageManager.PERMISSION_GRANTED) {
            return;
        }

        Intent intent = new Intent(this, MainActivity.class);
        intent.setFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        PendingIntent pendingIntent = PendingIntent.getActivity(
                this,
                notificationId,
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );

        NotificationCompat.Builder builder = new NotificationCompat.Builder(this, ALERT_CHANNEL_ID)
                .setSmallIcon(R.mipmap.ic_launcher)
                .setContentTitle(title)
                .setContentText(message)
                .setStyle(new NotificationCompat.BigTextStyle().bigText(message))
                .setPriority(NotificationCompat.PRIORITY_MAX)
                .setCategory(NotificationCompat.CATEGORY_ALARM)
                .setAutoCancel(true)
                .setContentIntent(pendingIntent)
                .setDefaults(NotificationCompat.DEFAULT_ALL);

        NotificationManagerCompat.from(this).notify(notificationId, builder.build());
    }

    private void updateLightCard(android.view.View card, ImageButton button, TextView stateText, boolean isOn, boolean shouldAnimate) {
        card.setBackgroundColor(isOn ? LIGHT_ON_CARD_BG : LIGHT_OFF_CARD_BG);
        button.setColorFilter(isOn ? LIGHT_ON_ICON_COLOR : LIGHT_OFF_ICON_COLOR);
        stateText.setText(isOn ? "BẬT" : "TẮT");
        stateText.setTextColor(isOn ? LIGHT_ON_TEXT_COLOR : LIGHT_OFF_TEXT_COLOR);

        if (shouldAnimate) {
            runLightStateAnimation(card, button);
        }
    }

    private void runLightStateAnimation(android.view.View card, ImageButton button) {
        ObjectAnimator cardBlink = ObjectAnimator.ofFloat(card, "alpha", 1f, 0.65f, 1f);
        cardBlink.setDuration(300);

        ObjectAnimator iconPulseX = ObjectAnimator.ofFloat(button, "scaleX", 1f, 1.12f, 1f);
        iconPulseX.setDuration(300);

        ObjectAnimator iconPulseY = ObjectAnimator.ofFloat(button, "scaleY", 1f, 1.12f, 1f);
        iconPulseY.setDuration(300);

        cardBlink.start();
        iconPulseX.start();
        iconPulseY.start();
    }

    private void applyDeviceNamesFromSensorResponse(JSONObject data) {
        JSONObject namesObj = data.optJSONObject("device_names");
        if (namesObj == null) {
            return;
        }

        boolean hasChange = false;
        for (String key : DEVICE_KEYS) {
            String incoming = namesObj.optString(key, "").trim();
            if (!incoming.isEmpty()) {
                String current = deviceNameMap.get(key);
                if (!incoming.equals(current)) {
                    deviceNameMap.put(key, incoming);
                    hasChange = true;
                }
            }
        }

        if (hasChange) {
            cacheDeviceNames();
            applyDeviceNamesToUi();
            applySelectedDeviceName();
            tvDeviceNameStatus.setText("Đã đồng bộ tên thiết bị từ MongoDB qua server.");
        }
    }

    private void postJson(String endpoint, JSONObject body, String successMessage) {
        RequestBody requestBody = RequestBody.create(body.toString(), JSON);
        Request request = new Request.Builder()
                .url(getBaseUrl() + endpoint)
                .post(requestBody)
                .build();

        setStatus("Đang gửi lệnh...");

        httpClient.newCall(request).enqueue(new Callback() {
            @Override
            public void onFailure(Call call, IOException e) {
                showError("Request failed: " + e.getMessage() + getConnectionHint());
            }

            @Override
            public void onResponse(Call call, Response response) throws IOException {
                String responseBody = response.body() != null ? response.body().string() : "";
                if (!response.isSuccessful()) {
                    showError("Server error " + response.code() + ": " + responseBody);
                    return;
                }

                runOnUiThread(() -> {
                    setStatus(successMessage);
                    Toast.makeText(MainActivity.this, successMessage, Toast.LENGTH_SHORT).show();
                    fetchLatestSensor();
                });
            }
        });
    }

    private void loadDeviceNames() {
        Request request = new Request.Builder()
                .url(getBaseUrl() + "/devices/names")
                .get()
                .build();

        httpClient.newCall(request).enqueue(new Callback() {
            @Override
            public void onFailure(Call call, IOException e) {
                runOnUiThread(() -> tvDeviceNameStatus.setText("Không tải được tên thiết bị."));
            }

            @Override
            public void onResponse(Call call, Response response) throws IOException {
                String responseBody = response.body() != null ? response.body().string() : "";
                if (!response.isSuccessful()) {
                    runOnUiThread(() -> tvDeviceNameStatus.setText("Không tải được tên thiết bị."));
                    return;
                }

                try {
                    JSONObject result = new JSONObject(responseBody);
                    if (!result.optBoolean("success", false)) {
                        runOnUiThread(() -> tvDeviceNameStatus.setText("Không tải được tên thiết bị."));
                        return;
                    }

                    JSONArray items = result.optJSONArray("items");
                    deviceNameMap.clear();
                    if (items != null) {
                        for (int i = 0; i < items.length(); i++) {
                            JSONObject item = items.optJSONObject(i);
                            if (item == null) {
                                continue;
                            }
                            String key = item.optString("device", "").trim();
                            String displayName = item.optString("display_name", "").trim();
                            if (!key.isEmpty() && !displayName.isEmpty()) {
                                deviceNameMap.put(key, displayName);
                            }
                        }
                    }

                    cacheDeviceNames();
                    runOnUiThread(() -> {
                        applyDeviceNamesToUi();
                        applySelectedDeviceName();
                        tvDeviceNameStatus.setText("Đã tải tên thiết bị từ MongoDB.");
                    });
                } catch (Exception e) {
                    runOnUiThread(() -> tvDeviceNameStatus.setText("Không tải được tên thiết bị."));
                }
            }
        });
    }

    private void saveDeviceName() {
        String deviceKey = getSelectedDeviceKey();
        String displayName = etDeviceName.getText().toString().trim();

        if (displayName.isEmpty()) {
            showError("Vui lòng nhập tên thiết bị");
            return;
        }

        try {
            JSONObject body = new JSONObject();
            body.put("device", deviceKey);
            body.put("display_name", displayName);

            Request request = new Request.Builder()
                    .url(getBaseUrl() + "/devices/names")
                    .post(RequestBody.create(body.toString(), JSON))
                    .build();

            setStatus("Đang lưu tên thiết bị...");

            httpClient.newCall(request).enqueue(new Callback() {
                @Override
                public void onFailure(Call call, IOException e) {
                    showError("Lưu tên thiết bị thất bại: " + e.getMessage());
                }

                @Override
                public void onResponse(Call call, Response response) throws IOException {
                    String responseBody = response.body() != null ? response.body().string() : "";
                    if (!response.isSuccessful()) {
                        showError("Lưu tên thiết bị thất bại: " + responseBody);
                        return;
                    }

                    deviceNameMap.put(deviceKey, displayName);
                    cacheDeviceNames();
                    runOnUiThread(() -> {
                        applyDeviceNamesToUi();
                        tvDeviceNameStatus.setText("Đã lưu tên cho " + fallbackName(deviceKey) + ": " + displayName);
                        setStatus("Đã lưu tên thiết bị");
                        Toast.makeText(MainActivity.this, "Đã lưu tên thiết bị", Toast.LENGTH_SHORT).show();
                    });
                }
            });
        } catch (Exception e) {
            showError("Không thể tạo request lưu tên: " + e.getMessage());
        }
    }

    private void applySelectedDeviceName() {
        String key = getSelectedDeviceKey();
        etDeviceName.setText(deviceNameMap.getOrDefault(key, ""));
    }

    private String getSelectedDeviceKey() {
        int index = spDeviceKey.getSelectedItemPosition();
        if (index < 0 || index >= DEVICE_KEYS.length) {
            return "door";
        }
        return DEVICE_KEYS[index];
    }

    private void applyDeviceNamesToUi() {
        String doorName = getDeviceDisplayName("door", "Cửa");
        String fanName = getDeviceDisplayName("fan", "Quạt");
        String roofName = getDeviceDisplayName("roof", "Mái che");
        String light1Name = getDeviceDisplayName("light1", "Đèn 1");
        String light2Name = getDeviceDisplayName("light2", "Đèn 2");
        String light3Name = getDeviceDisplayName("light3", "Đèn 3");
        String light4Name = getDeviceDisplayName("light4", "Đèn 4");

        tvStatusDoorTitle.setText("🚪 " + doorName);
        tvStatusFanTitle.setText("🌀 " + fanName);
        tvDoorPanelTitle.setText("🚪 Điều khiển " + doorName.toLowerCase(Locale.US));
        tvDoorPasswordLabel.setText("Mật khẩu mở " + doorName.toLowerCase(Locale.US));
        tvFanControlLabel.setText(fanName);
        tvRoofControlLabel.setText(roofName);

        tvLight1Name.setText(light1Name);
        tvLight2Name.setText(light2Name);
        tvLight3Name.setText(light3Name);
        tvLight4Name.setText(light4Name);

        setupDeviceSpinner();
    }

    private String getDeviceDisplayName(String key, String fallback) {
        String name = deviceNameMap.get(key);
        return (name == null || name.trim().isEmpty()) ? fallback : name;
    }

    private String fallbackName(String key) {
        switch (key) {
            case "door":
                return "Cửa";
            case "fan":
                return "Quạt";
            case "roof":
                return "Mái che";
            case "light1":
                return "Đèn 1";
            case "light2":
                return "Đèn 2";
            case "light3":
                return "Đèn 3";
            case "light4":
                return "Đèn 4";
            default:
                return key;
        }
    }

    private void loadCachedDeviceNames() {
        String json = getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
                .getString(KEY_DEVICE_NAMES_JSON, "{}");
        try {
            JSONObject cached = new JSONObject(json);
            deviceNameMap.clear();
            for (String key : DEVICE_KEYS) {
                String value = cached.optString(key, "").trim();
                if (!value.isEmpty()) {
                    deviceNameMap.put(key, value);
                }
            }
        } catch (Exception ignored) {
        }
    }

    private void cacheDeviceNames() {
        try {
            JSONObject cache = new JSONObject();
            for (String key : DEVICE_KEYS) {
                String value = deviceNameMap.get(key);
                if (value != null) {
                    cache.put(key, value);
                }
            }
            getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
                    .edit()
                    .putString(KEY_DEVICE_NAMES_JSON, cache.toString())
                    .apply();
        } catch (Exception ignored) {
        }
    }

    private void updateConnectionUi(boolean connected) {
        if (connected) {
            tvConnectionStatus.setText("✓ Đã kết nối");
            tvConnectionStatus.setBackgroundColor(0xFF27AE60);
        } else {
            tvConnectionStatus.setText("⚠ Chưa có dữ liệu");
            tvConnectionStatus.setBackgroundColor(0xFFD64545);
        }
    }

    private void setAlertColor(TextView view, boolean alert) {
        view.setTextColor(alert ? 0xFFE74C3C : 0xFF27AE60);
    }

    private String formatOneDecimal(double value) {
        return String.format(Locale.US, "%.1f", value);
    }

    private String formatTimestamp(String input) {
        try {
            if (input.contains("T")) {
                return input.replace("T", " ");
            }
            return input;
        } catch (Exception e) {
            return new SimpleDateFormat("dd/MM/yyyy HH:mm:ss", Locale.US).format(new Date());
        }
    }

    private boolean isDoorOpenState(Object value) {
        if (value == null) {
            return false;
        }
        if (value instanceof Boolean) {
            return (Boolean) value;
        }
        if (value instanceof Number) {
            return ((Number) value).intValue() == 1;
        }
        String text = String.valueOf(value).trim().toLowerCase(Locale.US);
        return "open".equals(text) || "1".equals(text) || "true".equals(text);
    }

    private void startPolling() {
        pollingHandler.removeCallbacks(pollSensorTask);
        pollingHandler.postDelayed(pollSensorTask, POLLING_INTERVAL_MS);
    }

    private void setStatus(String text) {
        runOnUiThread(() -> tvStatus.setText("Status: " + text));
    }

    private void showError(String message) {
        runOnUiThread(() -> {
            tvStatus.setText("Status: ERROR - " + message);
            Toast.makeText(MainActivity.this, message, Toast.LENGTH_LONG).show();
            tvConnectionStatus.setText("✗ Lỗi kết nối");
            tvConnectionStatus.setBackgroundColor(0xFFD64545);
        });
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        pollingHandler.removeCallbacks(pollSensorTask);
        if (textToSpeech != null) {
            textToSpeech.stop();
            textToSpeech.shutdown();
        }
    }
}