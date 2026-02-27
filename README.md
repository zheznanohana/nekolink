# 🐾 NekoLink

> iPhone ANCS Notification Bridge for Windows  
> iPhone → Windows → Telegram / Email  

---

# 🇨🇳 中文介绍

## ✨ 项目简介

**NekoLink** 是一个 Windows 桌面程序，通过蓝牙低功耗（BLE）连接 iPhone，  
使用 **ANCS（Apple Notification Center Service）协议** 获取系统通知，  
并将通知转发到：

- Telegram Bot
- Email（SMTP）

适用于：

- 留学 / 海外工作场景
- iphone留在家中
- 远程接收短信验证码/通知
- 全量通知同步

---

## 🧠 工作原理

NekoLink 通过：

1. Windows 使用 BLE 连接 iPhone
2. 订阅 ANCS Notification Source
3. 通过 Control Point 拉取通知文本
4. 解析内容
5. 通过 Telegram Bot API / SMTP 转发

Windows 端模拟类似 Apple Watch 的行为，  
订阅 iPhone 的系统通知流。

---

## ⚠ 重要前置条件（必须）

在使用前，请先：

### 1️⃣ 安装 LightBlue（iPhone 端）

你需要在 iPhone 上安装：

> **LightBlue® — Bluetooth Low Energy**并选择virtual service，添加一个heartrate设备

用途：

- 维持 BLE 长连接
- 保持 iOS 不杀后台
- 作为“心率设备”广播

否则 ANCS 连接可能不稳定。

---

### 2️⃣ iPhone 设置

- 打开 蓝牙
- 设置 → 蓝牙 → 允许共享系统通知
- 首次连接时点击“配对”

---

### 3️⃣ Windows 要求

- Windows 10 / 11
- 蓝牙 4.0+
- 支持 BLE

---

## 🚀 使用步骤

### 第一步：扫描设备

1. 打开 NekoLink
2. 进入 Devices 页面
3. 点击 Scan
4. 找到 “Heart Rate” 设备
5. 添加地址

---

### 第二步：配置 Telegram

1. 创建 Telegram Bot（@BotFather）
2. 获取 Bot Token
3. 获取 Chat ID
4. 填入 Destinations 页面
5. 点击 Save
6. 点击 Test 测试

---

### 第三步：启动

点击：
开始

触发 iPhone 通知测试。

---


## 🛡 安全说明

- 本软件仅使用 Apple 官方 ANCS 协议
- 不越狱
- 不绕过 iOS 安全机制
- 不访问私有 API

---

# 🇺🇸 English Description

## ✨ Overview

**NekoLink** is a Windows desktop application that connects to an iPhone via  
Bluetooth Low Energy (BLE) using the **Apple Notification Center Service (ANCS)** protocol.

It forwards notifications to:

- Telegram Bot
- Email (SMTP)

Designed for:

- Studying / working abroad
- Leaving a iphone at home
- Remote verification code reception
- Full notification forwarding

---

## 🧠 How It Works

1. Windows connects to iPhone via BLE
2. Subscribes to ANCS Notification Source
3. Uses Control Point to fetch notification text
4. Parses payload
5. Sends via Telegram Bot API or SMTP

Windows acts similarly to an Apple Watch subscribing to system notifications.

---

## ⚠ Requirements

### 1️⃣ Install LightBlue on iPhone

Required app:

> **LightBlue® — Bluetooth Low Energy** and slect virtual service and add a heart rate

Purpose:

- Maintain stable BLE connection
- Prevent iOS background termination
- Advertise as Heart Rate device

Without this, connection stability may decrease.

---

### 2️⃣ iPhone Settings

- Enable Bluetooth
- Allow notification sharing
- Accept pairing request

---

### 3️⃣ Windows Requirements

- Windows 10 / 11
- Bluetooth 4.0+
- BLE support

---

## 🚀 Usage

### Step 1: Scan Device

- Open NekoLink
- Go to Devices
- Click Scan
- Find “Heart Rate” device
- Add address

### Step 2: Configure Telegram

- Create bot via @BotFather
- Get Bot Token
- Get Chat ID
- Fill in Destinations
- Save
- Test

### Step 3: Start

Click:
START

Trigger an iPhone notification to test.

---

## 🙏 Acknowledgements

This project was inspired by the concept of **CatConnect**,  
which explores cross-device notification synchronization.

NekoLink is independently implemented using ANCS on Windows.  
Respect to the original author for the inspiration.

---

## 📜 License

MIT License

---

## ⚠ Disclaimer

This software uses Apple's public ANCS protocol.  
It does not bypass iOS sandbox or security restrictions.

Use responsibly.
