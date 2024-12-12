[app]
# (str) Title of your application
title = GpsRecorder

# (str) Package name
package.name = gps_recorder

# (str) Source code where the main.py live
source.dir = .

# (str) Package domain (needed for Android package name)
package.domain = rutter-moore.co.uk

# (str) Application versioning (method 1)
version = 0.0.1

# (list) Application requirements
requirements = kivy, plyer, requests, python-dotenv

# (str) The directory where your app should be built
source.include_exts = py,png,jpg,kv,atlas,env

# (bool) Whether the application should be run in debug mode
debug = True

# (str) Log level for Kivy
log_level = 2

# (str) Target platform (android, ios)
target = android

[buildozer]
# (str) Log level, change to 2 for debugging
log_level = 2

# (bool) Whether to start in debug mode
debug = True

# (str) Target platform (android, ios)
target = android

# (list) Permissions (for Android)
android.permissions = ACCESS_FINE_LOCATION, ACCESS_COARSE_LOCATION, INTERNET

[ios]
# (str) The list of additional frameworks to include in the app for iOS
ios.kivy_ios.additional_frameworks = CoreLocation, Foundation
ios.entitlements.usage_description = "This app uses location services to provide GPS data."
