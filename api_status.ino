/**
 * @file M5Stack_MQTT_Monitor.ino
 * @author lemonhall (lemonhall2012@qq.com)
 * @brief M5Stack CoreS3 MQTT Monitoring System with Tencent Support
 * @version 0.1
 * @date 2024-02-08
 *
 * @Hardwares: M5CoreS3
 * @Platform Version: Arduino M5Stack Board Manager v2.0.7
 * @Dependent Library:
 * M5GFX: <url id="cujn8vvahd8a82m4smg0" type="url" status="parsed" title="GitHub - m5stack/M5GFX: Graphics library for M5Stack series" wc="1165"><url id="" type="url" status="" title="" wc="">https://github.com/m5stack/M5GFX</url></url>  
 * M5Unified: <url id="cujn8vvahd8a82m4smgg" type="url" status="parsed" title="GitHub - m5stack/M5Unified: Unified library for M5Stack series" wc="23147"><url id="" type="url" status="" title="" wc="">https://github.com/m5stack/M5Unified</url></url>  
 * M5CoreS3: <url id="cujn8vvahd8a82m4smh0" type="url" status="parsed" title="GitHub - m5stack/M5CoreS3: M5CoreS3 Arduino Library" wc="5040"><url id="" type="url" status="" title="" wc="">https://github.com/m5stack/M5CoreS3</url></url>  
 */

 #include "M5CoreS3.h"
 #include <ArduinoJson.h>
 #include <WiFi.h>
 #include <PubSubClient.h>
 
 // MQTT配置
 WiFiClient espClient;
 PubSubClient client(espClient);
 const char* ssid        = "lemon_2.4";
 const char* password    = "xxxxxxxxxxxxxxxxxxx";
 const char* mqtt_server = "192.168.50.233";
 const int mqtt_port     = 1883;
 const char* mqtt_topic  = "api_status"; // MQTT主题
 
 // 屏幕绘制相关
 #define SCREEN_WIDTH 135
 #define SCREEN_HEIGHT 240
 #define CURVE_HISTORY 30 // 历史数据点数
 #define TEXT_SIZE 1.5
 
 // 服务状态
 struct ServiceStatus {
   bool online;
   float response_time;
   String error;
   unsigned long timestamp;
 };
 
 ServiceStatus deepseek = {false, 0, "", 0};
 ServiceStatus siliconflow = {false, 0, "", 0};
 ServiceStatus huoshan = {false, 0, "", 0};
 ServiceStatus tencent = {false, 0, "", 0}; // 腾讯服务状态
 ServiceStatus bailian = {false, 0, "", 0}; // Bailian 服务状态
 
 // 历史数据存储
 float deepseek_history[CURVE_HISTORY] = {0};
 float siliconflow_history[CURVE_HISTORY] = {0};
 float huoshan_history[CURVE_HISTORY] = {0};
 float tencent_history[CURVE_HISTORY] = {0}; // 腾讯历史数据数组
 float bailian_history[CURVE_HISTORY] = {0}; // Bailian 历史数据数组
 
 // 时间跟踪
 unsigned long lastRebootTime = 0;
 
 // MQTT回调函数
 void callback(char* topic, byte* payload, unsigned int length) {
   String message;
   for (unsigned int i = 0; i < length; i++) {
     message += (char)payload[i];
   }
 
   Serial.print("Message arrived [");
   Serial.print(topic);
   Serial.print("] ");
   Serial.println(message);
   // 解析JSON
   StaticJsonDocument<512> doc;
 
   // 解析JSON值
   DeserializationError deserial_error = deserializeJson(doc, message);
   if (deserial_error) {
     Serial.print("JSON Parsing Error: ");
     Serial.println(deserial_error.c_str());
     return;
   }
 
   String provider = doc["provider"].as<String>();
   bool online = doc["online"].as<bool>();
   float response_time = doc["response_time"].as<float>();
   String error_msg = doc["error"].as<String>();
   unsigned long timestamp = doc["timestamp"].as<unsigned long>();
 
   Serial.print("Provider: ");
   Serial.println(provider);
   Serial.print("Online: ");
   Serial.println(online);
   Serial.print("Response Time: ");
   Serial.println(response_time);
   Serial.print("Error: ");
   Serial.println(error_msg);
 
   // 更新状态和历史数组
   if (provider == "deepseek") {
     deepseek.online = online;
     deepseek.response_time = response_time;
     deepseek.error = error_msg;
     deepseek.timestamp = timestamp;
 
     // 更新 deepseek_history
     for (int i = 0; i < CURVE_HISTORY - 1; i++) {
       deepseek_history[i] = deepseek_history[i + 1];
     }
     deepseek_history[CURVE_HISTORY - 1] = response_time;
   } else if (provider == "siliconflow") {
     siliconflow.online = online;
     siliconflow.response_time = response_time;
     siliconflow.error = error_msg;
     siliconflow.timestamp = timestamp;
 
     // 更新 siliconflow_history
     for (int i = 0; i < CURVE_HISTORY - 1; i++) {
       siliconflow_history[i] = siliconflow_history[i + 1];
     }
     siliconflow_history[CURVE_HISTORY - 1] = response_time;
   } else if (provider == "huoshan") {
     huoshan.online = online;
     huoshan.response_time = response_time;
     huoshan.error = error_msg;
     huoshan.timestamp = timestamp;
 
     // 更新 huoshan_history
     for (int i = 0; i < CURVE_HISTORY - 1; i++) {
       huoshan_history[i] = huoshan_history[i + 1];
     }
     huoshan_history[CURVE_HISTORY - 1] = response_time;
   } else if (provider == "tencent") { // 华为更新逻辑
     tencent.online = online;
     tencent.response_time = response_time;
     tencent.error = error_msg;
     tencent.timestamp = timestamp;
 
     // 更新 tencent_history
     for (int i = 0; i < CURVE_HISTORY - 1; i++) {
       tencent_history[i] = tencent_history[i + 1];
     }
     tencent_history[CURVE_HISTORY - 1] = response_time;
   } else if (provider == "bailian") { // Bailian 更新逻辑
     bailian.online = online;
     bailian.response_time = response_time;
     bailian.error = error_msg;
     bailian.timestamp = timestamp;
 
     // 更新 bailian_history
     for (int i = 0; i < CURVE_HISTORY -1; i++) {
       bailian_history[i] = bailian_history[i+1];
     }
     bailian_history[CURVE_HISTORY -1] = response_time;
   }
 }
 
 // 重新连接WiFi和MQTT
 void reConnect() {
   while (WiFi.status() != WL_CONNECTED) {
     delay(500);
     Serial.print(".");
   }
   Serial.println("\nWiFi Connected");
 
   while (!client.connected()) {
     Serial.print("Attempting MQTT connection...");
     String clientId = "M5Stack-";
     clientId += String(random(0xffff), HEX);
     if (client.connect(clientId.c_str())) {
       Serial.println("connected");
       client.subscribe(mqtt_topic);
     } else {
       Serial.print("failed, rc=");
       Serial.print(client.state());
       Serial.println(" try again in 5 seconds");
       delay(5000);
     }
   }
 }
 
 // 初始化函数
 void setup() {
   auto cfg = M5.config();
   Serial.begin(115200); // 初始化串口，波特率为 115200
   CoreS3.begin(cfg);
   setupWifi();
 
   // 初始化MQTT客户端
   client.setServer(mqtt_server, mqtt_port);
   client.setCallback(callback);
 
   // 初始化上次重启时间
   lastRebootTime = millis();
 }
 
 // Wi-Fi连接设置
 void setupWifi() {
   delay(10);
   CoreS3.Lcd.print("Connecting to Network...");
   Serial.printf("Connecting to %s", ssid);
   WiFi.mode(WIFI_STA);
   WiFi.begin(ssid, password);
 
   while (WiFi.status() != WL_CONNECTED) {
     delay(500);
     Serial.print(".");
   }
   Serial.printf("\nWiFi Connected\n");
   CoreS3.Lcd.println("WiFi Connected");
   CoreS3.Lcd.fillScreen(BLACK);
 }
 
 // 绘制服务状态
 void drawService(String name, ServiceStatus status, int x, int y) {
   CoreS3.Lcd.setTextDatum(CC_DATUM);
   CoreS3.Lcd.setTextColor(status.online ? GREEN : RED);
   CoreS3.Lcd.drawString(name, x + 50, y + 5);
   Serial.println(name);
   Serial.print("online: ");
   Serial.println(status.online);
   Serial.print("response_time: ");
   Serial.println(status.response_time);
   Serial.print("error: ");
   Serial.println(status.error);
   Serial.print("timestamp: ");
   Serial.println(status.timestamp);
 
   if (!status.online) {
     CoreS3.Lcd.setTextColor(RED);
     CoreS3.Lcd.drawString(status.error, x + 50, y + 20);
   } else {
     CoreS3.Lcd.setTextColor(WHITE);
     CoreS3.Lcd.drawString(String(status.response_time) + "ms", x + 50, y + 20);
   }
 }
 
 // 打印历史数据点到串口
 void printHistoryArray(float history[], int length) {
   Serial.print("History Array:");
   Serial.print("[");
   for (int i = 0; i < length; i++) {
     Serial.print(history[i]);
     Serial.print(",");
   }
   Serial.println("]");
 }
 
 // 绘制曲线
 void drawCurve(float history[], uint16_t color, int x, int y, int length) {
   CoreS3.Lcd.drawRect(x, y, SCREEN_WIDTH - 20, 30, color);
 
   printHistoryArray(history, length);
 
   for (int i = 0; i < length; i++) {
     int pos = x + (i * (SCREEN_WIDTH - 20) / length);
     int height = map(history[i], 0, 30000, 0, 30); // 假设响应时间最大为30秒
 
     // 绘制点
     CoreS3.Lcd.fillCircle(pos, y + 15 - height, 3, color);
 
     // 绘制连线
     if (i > 0) {
       int prev_pos = x + ((i - 1) * (SCREEN_WIDTH - 20) / length);
       int prev_height = map(history[i - 1], 0, 30000, 0, 30);
       CoreS3.Lcd.drawLine(pos, y + 15 - height, prev_pos, y + 15 - prev_height, color);
     }
   }
 }
 
 // 主循环
 void loop() {
   if (!client.connected()) {
     reConnect();
   }
   client.loop();
 
   // 更新屏幕
   updateScreen();
 
   // 定期重启设备
   if (millis() - lastRebootTime > 3600000) {
     ESP.restart();
   }
 
   delay(3000); // 更新频率
 }
 
 // 更新屏幕显示
 void updateScreen() {
   CoreS3.Lcd.setRotation(1); // 横屏显示
   CoreS3.Lcd.fillScreen(BLACK);
 
   // 绘制服务状态
   drawService("DeepSeek", deepseek, 10, 10);
   drawService("SiliconFlow", siliconflow, 10, 50);
   drawService("Huoshan", huoshan, 10, 90);
   drawService("Tencent", tencent, 10, 130); // 腾讯服务状态绘制
   drawService("Bailian", bailian, 10, 170); // Bailian 服务状态绘制
 
   // 绘制曲线
   drawCurve(deepseek_history, RED, 190, 10, CURVE_HISTORY);
   drawCurve(siliconflow_history, GREEN, 190, 50, CURVE_HISTORY);
   drawCurve(huoshan_history, BLUE, 190, 90, CURVE_HISTORY);
   drawCurve(tencent_history, YELLOW, 190, 130, CURVE_HISTORY); // 腾讯曲线绘制
   drawCurve(bailian_history, CYAN, 190, 170, CURVE_HISTORY); // Bailian 曲线绘制
 }