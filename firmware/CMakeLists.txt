# ESP-IDF project: Arduino core 3 runs as an IDF component, so the settings
# in sdkconfig.defaults apply (PlatformIO generates sdkconfig.<env> from it).
cmake_minimum_required(VERSION 3.22)
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(aware-bin)
