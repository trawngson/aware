# AWARE - React Native Starter

AWARE is a YOLO-driven trash identification mobile app based on the COCO and TACO dataset.

## Description

This is a React Native starter application for building a mobile app that uses computer vision to identify and classify trash for environmental awareness and recycling purposes.

## Prerequisites

- Node.js >= 20
- npm or yarn
- React Native development environment set up:
  - For iOS: macOS with Xcode installed
  - For Android: Android Studio with Android SDK

## Installation

1. Clone the repository:
```bash
git clone https://github.com/trawngson/aware.git
cd aware
```

2. Install dependencies:
```bash
npm install
# or
yarn install
```

3. For iOS (macOS only):
```bash
cd ios && pod install && cd ..
```

## Running the App

### Android

```bash
npm run android
# or
yarn android
```

Make sure you have an Android emulator running or a physical device connected.

### iOS (macOS only)

```bash
npm run ios
# or
yarn ios
```

Make sure you have an iOS simulator running or a physical device connected.

### Development Server

Start the Metro bundler:
```bash
npm start
# or
yarn start
```

## Available Scripts

- `npm start` - Start the Metro bundler
- `npm run android` - Run the app on Android
- `npm run ios` - Run the app on iOS
- `npm test` - Run tests
- `npm run lint` - Run ESLint

## Project Structure

```
aware/
├── android/          # Android native code
├── ios/              # iOS native code
├── __tests__/        # Test files
├── App.tsx           # Main application component
├── index.js          # Application entry point
└── package.json      # Dependencies and scripts
```

## Future Features

- [ ] YOLO model integration for object detection
- [ ] Camera integration for real-time trash identification
- [ ] Database of trash items from COCO and TACO datasets
- [ ] Classification and recycling instructions
- [ ] User interface for displaying results

## License

MIT License - see LICENSE file for details.
