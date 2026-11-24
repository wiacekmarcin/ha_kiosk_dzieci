package pl.mieszkanie.hakioskdzieci;

import android.app.admin.DeviceAdminReceiver;

/**
 * Administrator urządzenia dla trybu kiosku. Gdy aplikacja jest właścicielem urządzenia
 * (adb shell dpm set-device-owner pl.mieszkanie.hakioskdzieci/.AdminReceiver), kod w
 * Pythonie (dzieci/kiosklock.py) zezwala sobie na tryb zadania zablokowanego - przypięcie
 * jest wtedy ciche i nie da się go zdjąć gestem - oraz ustawia aplikację jako stały ekran
 * główny. Sama klasa nie musi nic robić.
 */
public class AdminReceiver extends DeviceAdminReceiver {
}
