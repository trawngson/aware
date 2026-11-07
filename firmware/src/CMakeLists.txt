# Every source file in src/. camera_esp32.cpp and camera_sim.cpp compile to
# nothing outside their own build (AWARE_SIMULATOR decides).
file(GLOB app_sources ${CMAKE_CURRENT_SOURCE_DIR}/*.cpp)
set(include_dirs "../include")
# The simulator's photo header, made by scripts/sim_photos.py
if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/../sim/generated")
  list(APPEND include_dirs "../sim/generated")
endif()
idf_component_register(SRCS ${app_sources}
                       INCLUDE_DIRS ${include_dirs})
