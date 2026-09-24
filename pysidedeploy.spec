[app]

# title of your application
title = NetConfigLint

# project root directory. default = The parent directory of input_file
project_dir = .

# source file entry point path. default = main.py
input_file = netconfiglint\deploy_main.py

# directory where the executable output is generated
exec_directory = dist

# path to the project file relative to project_dir
project_file = 

# application icon
icon = netconfiglint\resources\icons\app.ico

[python]

# python path
python_path = .venv\Scripts\python.exe

# python packages to install
packages = Nuitka==4.2

# buildozer = for deploying Android application
android_packages = buildozer==1.5.0,cython==0.29.33

[qt]

# paths to required qml files. comma separated
# normally all the qml files required by the project are added automatically
# design studio projects include the qml files using qt resources
qml_files = netconfiglint\gui\qml\analysis\AnalysisPanel.qml,netconfiglint\gui\qml\analysis\IssueCard.qml,netconfiglint\gui\qml\analysis\IssueList.qml,netconfiglint\gui\qml\components\AppButton.qml,netconfiglint\gui\qml\components\AppCard.qml,netconfiglint\gui\qml\components\AppDialog.qml,netconfiglint\gui\qml\components\AppMenu.qml,netconfiglint\gui\qml\components\AppScrollBar.qml,netconfiglint\gui\qml\components\AppTextField.qml,netconfiglint\gui\qml\components\AppTitleBar.qml,netconfiglint\gui\qml\components\AppToast.qml,netconfiglint\gui\qml\components\CardHeader.qml,netconfiglint\gui\qml\components\EmptyState.qml,netconfiglint\gui\qml\components\SelectableText.qml,netconfiglint\gui\qml\components\SelectionDialog.qml,netconfiglint\gui\qml\components\SelectionField.qml,netconfiglint\gui\qml\components\StatusBadge.qml,netconfiglint\gui\qml\components\TextEditMenu.qml,netconfiglint\gui\qml\config\ConfigEditor.qml,netconfiglint\gui\qml\config\ConfigToolbar.qml,netconfiglint\gui\qml\config\ExportDialog.qml,netconfiglint\gui\qml\Main.qml,netconfiglint\gui\qml\navigation\NavigationItem.qml,netconfiglint\gui\qml\navigation\NavigationRail.qml,netconfiglint\gui\qml\pages\AboutPage.qml,netconfiglint\gui\qml\pages\ConfigCheckPage.qml,netconfiglint\gui\qml\pages\SettingsPage.qml,netconfiglint\gui\qml\theme\Colors.qml,netconfiglint\gui\qml\theme\Spacing.qml,netconfiglint\gui\qml\theme\Theme.qml,netconfiglint\gui\qml\theme\Typography.qml

# excluded qml plugin binaries
excluded_qml_plugins = QtCharts,QtSensors,QtWebEngine

# qt modules used. comma separated
modules = Core,Gui,Qml,Quick,QuickControls2

# qt plugins used by the application. only relevant for desktop deployment
# for qt plugins used in android application see [android][plugins]
plugins = accessiblebridge,egldeviceintegrations,generic,iconengines,imageformats,platforminputcontexts,platforms,platforms/darwin,platformthemes,qmllint,qmltooling,scenegraph,vectorimageformats,wayland-decoration-client,wayland-graphics-integration-client,wayland-shell-integration,xcbglintegrations

[android]

# path to pyside wheel
wheel_pyside = 

# path to shiboken wheel
wheel_shiboken = 

# plugins to be copied to libs folder of the packaged application. comma separated
plugins = 

[nuitka]

# usage description for permissions requested by the app as found in the info.plist file
# of the app bundle. comma separated
# eg = extra_args = --show-modules --follow-stdlib
macos.permissions = 

# mode of using nuitka. accepts standalone or onefile. default = onefile
mode = standalone

# specify any extra nuitka arguments
extra_args = --quiet --assume-yes-for-downloads --windows-console-mode=disable --product-name=NetConfigLint --product-version=2.1.0 --file-version=2.1.0 --file-description=NetConfigLint --noinclude-qt-translations --include-data-dir=netconfiglint/gui/qml=netconfiglint/gui/qml --include-data-dir=netconfiglint/gui/i18n=netconfiglint/gui/i18n --include-data-dir=netconfiglint/vendors/huawei/profiles=netconfiglint/vendors/huawei/profiles --include-data-dir=netconfiglint/resources=netconfiglint/resources

[buildozer]

# build mode
# possible values = ["aarch64", "armv7a", "i686", "x86_64"]
# release creates a .aab, while debug creates a .apk
mode = debug

# path to pyside6 and shiboken6 recipe dir
recipe_dir = 

# path to extra qt android .jar files to be loaded by the application
jars_dir = 

# if empty, uses default ndk path downloaded by buildozer
ndk_path = 

# if empty, uses default sdk path downloaded by buildozer
sdk_path = 

# other libraries to be loaded at app startup. comma separated.
local_libs = 

# architecture of deployed platform
arch = 
