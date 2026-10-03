cmake_minimum_required(VERSION 3.21)

# The version lives in plugin.json only; the app passes it back in initialize.
project(MegaDirStatPlugin LANGUAGES CXX)

# scripts/deploy.ps1 installs into the plugin folder's bin/, flat: the exe next
# to Qt's DLLs. Must precede qt_standard_project_setup(), whose GNUInstallDirs
# only fills in defaults.
set(CMAKE_INSTALL_BINDIR ".")

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(Qt6 6.8 REQUIRED COMPONENTS Core Gui Widgets Test)
qt_standard_project_setup()

add_library(DirStatWarnings INTERFACE)
# /external:W0: MSVC ignores the SYSTEM-ness of Qt's include dirs until an
# external warning level is set.
target_compile_options(DirStatWarnings INTERFACE
    /W4 /external:W0 /permissive- /utf-8 /Zc:__cplusplus)

# No Widgets: the snapshot model, the treemap layout and the tree builder.
qt_add_library(DirStatCore STATIC
    src/core/AccountSnapshot.h
    src/core/IAccountSource.h
    src/core/SizeNode.h src/core/SizeNode.cpp
    src/core/TreeBuilder.h src/core/TreeBuilder.cpp
    src/core/TreemapLayout.h src/core/TreemapLayout.cpp
)
target_include_directories(DirStatCore PUBLIC src)
target_link_libraries(DirStatCore PUBLIC Qt6::Core PRIVATE DirStatWarnings)

qt_add_executable(MegaDirStatPlugin WIN32
    main.cpp
    src/plugin/PluginAccountSource.h src/plugin/PluginAccountSource.cpp
    src/plugin/PluginHost.h src/plugin/PluginHost.cpp
    src/plugin/RpcChannel.h src/plugin/RpcChannel.cpp
    src/ui/LoadingView.h src/ui/LoadingView.cpp
    src/ui/MainWindow.h src/ui/MainWindow.cpp
    src/ui/PercentBarDelegate.h src/ui/PercentBarDelegate.cpp
    src/ui/SizeTreeModel.h src/ui/SizeTreeModel.cpp
    src/ui/TreemapWidget.h src/ui/TreemapWidget.cpp
    resources/appicon.rc
)
qt_add_resources(MegaDirStatPlugin appicon
    PREFIX /
    FILES
        resources/appicon-16.png
        resources/appicon-24.png
        resources/appicon-32.png
        resources/appicon-48.png
        resources/appicon-64.png
        resources/appicon-256.png)
target_link_libraries(MegaDirStatPlugin PRIVATE DirStatCore Qt6::Widgets DirStatWarnings)

enable_testing()
function(dirstat_add_test name)
    qt_add_executable(${name} ${ARGN})
    target_link_libraries(${name} PRIVATE DirStatCore Qt6::Test DirStatWarnings)
    add_test(NAME ${name} COMMAND ${name})
    # Qt's DLLs are not next to the test binaries.
    set_tests_properties(${name} PROPERTIES
        ENVIRONMENT_MODIFICATION "PATH=path_list_prepend:$<TARGET_FILE_DIR:Qt6::Core>")
endfunction()
dirstat_add_test(tst_sizenode tests/tst_sizenode.cpp)
dirstat_add_test(tst_treemaplayout tests/tst_treemaplayout.cpp)
dirstat_add_test(tst_treebuilder tests/tst_treebuilder.cpp)

# The exe end to end over stdio, as MEGA Explorer drives it; windowless.
find_package(Python3 COMPONENTS Interpreter)
if(Python3_Interpreter_FOUND)
    add_test(NAME protocol
        COMMAND ${Python3_EXECUTABLE} -m unittest -v test_protocol
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/tests)
    set_tests_properties(protocol PROPERTIES ENVIRONMENT_MODIFICATION
        "PATH=path_list_prepend:$<TARGET_FILE_DIR:Qt6::Core>;MEGADIRSTAT_PLUGIN_EXE=set:$<TARGET_FILE:MegaDirStatPlugin>;QT_QPA_PLATFORM=set:offscreen")
endif()

install(TARGETS MegaDirStatPlugin RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
qt_generate_deploy_app_script(
    TARGET MegaDirStatPlugin
    OUTPUT_SCRIPT DIRSTAT_DEPLOY_SCRIPT
    NO_TRANSLATIONS
    NO_COMPILER_RUNTIME
    NO_UNSUPPORTED_PLATFORM_ERROR
    # A raster Widgets window drawing PNG icons needs only the platforms and styles
    # plugins; the rest (and the libraries they pull in) is two thirds of the size.
    DEPLOY_TOOL_OPTIONS
        --no-opengl-sw --no-system-d3d-compiler --no-system-dxc-compiler
        --skip-plugin-types generic,iconengines,imageformats,networkinformation,tls
        --no-network --no-pdf --no-svg)
install(SCRIPT ${DIRSTAT_DEPLOY_SCRIPT})
# windeployqt finds the MSVC redistributable only through %VCINSTALLDIR%, which
# an ordinary shell does not set; this module uses the configured toolchain.
set(CMAKE_INSTALL_SYSTEM_RUNTIME_DESTINATION ${CMAKE_INSTALL_BINDIR})
include(InstallRequiredSystemLibraries)
