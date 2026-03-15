package com.example.smarthome;

import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Intent;
import android.os.Build;

import androidx.core.app.NotificationCompat;
import androidx.core.app.NotificationManagerCompat;

import com.google.firebase.messaging.FirebaseMessagingService;
import com.google.firebase.messaging.RemoteMessage;

public class SmartHomeFirebaseMessagingService extends FirebaseMessagingService {

    private static final String ALERT_CHANNEL_ID = "smarthome_alerts";

    @Override
    public void onMessageReceived(RemoteMessage remoteMessage) {
        super.onMessageReceived(remoteMessage);

        String title = null;
        String body = null;

        if (remoteMessage.getNotification() != null) {
            title = remoteMessage.getNotification().getTitle();
            body = remoteMessage.getNotification().getBody();
        }

        if ((title == null || title.trim().isEmpty()) && remoteMessage.getData() != null) {
            title = remoteMessage.getData().get("title");
        }
        if ((body == null || body.trim().isEmpty()) && remoteMessage.getData() != null) {
            body = remoteMessage.getData().get("body");
        }

        if (title == null || title.trim().isEmpty()) {
            title = "⚠️ Cảnh báo nhà thông minh";
        }
        if (body == null || body.trim().isEmpty()) {
            body = "Phát hiện sự kiện nguy hiểm, hãy kiểm tra ngay.";
        }

        showNotification(title, body);
    }

    @Override
    public void onNewToken(String token) {
        super.onNewToken(token);
        PushTokenRegistrar.register(getApplicationContext(), token);
    }

    private void showNotification(String title, String message) {
        createAlertNotificationChannel();

        Intent intent = new Intent(this, MainActivity.class);
        intent.setFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        PendingIntent pendingIntent = PendingIntent.getActivity(
                this,
                (int) (System.currentTimeMillis() & 0xfffffff),
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

        NotificationManagerCompat.from(this).notify((int) (System.currentTimeMillis() & 0xfffffff), builder.build());
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
}
