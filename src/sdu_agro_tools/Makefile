PLUGINNAME = SDU_Agro_Tools

PY_FILES = \
	__init__.py \
	sdu_agro_tools.py \
	sdu_agro_tools_provider.py

UI_FILES = \
	cdc/cdc_toolbar_dialog.ui \
	crop_row_detector/crop_row_toolbar_dialog.ui \
	utils/task_progress_bar.ui

COMPILED_UI_FILES = \
	cdc/cdc_toolbar_dialog_ui.py \
	crop_row_detector/crop_row_toolbar_dialog_ui.py \
	utils/task_progress_bar_ui.py

EXTRAS = \
	metadata.txt \
	icon.png \
	sdu_logo_hs.jpg \
	requirements.txt

EXTRA_DIRS = \
	cdc \
	crop_row_detector \
	utils

COMPILED_RESOURCE_FILES = resources.py

PEP8EXCLUDE=pydev,resources.py,conf.py,third_party,ui

# QGISDIR points to the location where your plugin should be installed.
# This varies by platform, relative to your HOME directory:
#	* Linux:
#	  .local/share/QGIS/QGIS3/profiles/default/
#	* Mac OS X:
#	  Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins
#	* Windows:
#	  AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins'

QGISDIR=.local/share/QGIS/QGIS3/profiles/default/

#################################################
# Normally you would not need to edit below here
#################################################

RESOURCE_SRC=$(shell grep '^ *<file' resources.qrc | sed 's@</file>@@g;s/.*>//g' | tr '\n' ' ')

.PHONY: default
default:
	@echo While you can use make to build and deploy your plugin, pb_tool
	@echo is a much better solution.
	@echo A Python script, pb_tool provides platform independent management of
	@echo your plugins and runs anywhere.
	@echo You can install pb_tool using: pip install pb_tool
	@echo See https://g-sherman.github.io/plugin_build_tool/ for info.

compile: $(COMPILED_RESOURCE_FILES)

compile-ui: $(UI_FILES)
	@echo
	@echo "----------------------------"
	@echo "Compiling UI files to python"
	@echo "----------------------------"
	$(foreach UI_FILE,$(UI_FILES), pyuic5 -o $(UI_FILE:.ui=_ui.py) $(UI_FILE);)

%.py : %.qrc $(RESOURCES_SRC)
	pyrcc5 -o $*.py  $<

deploy: compile compile-ui
	@echo
	@echo "------------------------------------------"
	@echo "Deploying plugin to your qgis directory."
	@echo "------------------------------------------"
	# The deploy  target only works on unix like operating system where
	# the Python plugin directory is located at:
	# $(HOME)/$(QGISDIR)/python/plugins
	mkdir -p $(HOME)/$(QGISDIR)/python/plugins/$(PLUGINNAME)
	cp -vf $(PY_FILES) $(HOME)/$(QGISDIR)/python/plugins/$(PLUGINNAME)
	cp -vf $(COMPILED_RESOURCE_FILES) $(HOME)/$(QGISDIR)/python/plugins/$(PLUGINNAME)
	cp -vf $(EXTRAS) $(HOME)/$(QGISDIR)/python/plugins/$(PLUGINNAME)
	# Copy extra directories if any
	$(foreach EXTRA_DIR,$(EXTRA_DIRS), cp -R $(EXTRA_DIR) $(HOME)/$(QGISDIR)/python/plugins/$(PLUGINNAME)/;)


mock-deploy: compile compile-ui
	@echo
	@echo "------------------------------------------"
	@echo "Deploying plugin to temp directory."
	@echo "------------------------------------------"
	rm -fr $(CURDIR)/temp/$(PLUGINNAME)
	mkdir -p $(CURDIR)/temp/$(PLUGINNAME)
	cp -vf $(PY_FILES) $(CURDIR)/temp/$(PLUGINNAME)
	cp -vf $(COMPILED_RESOURCE_FILES) $(CURDIR)/temp/$(PLUGINNAME)
	cp -vf $(EXTRAS) $(CURDIR)/temp/$(PLUGINNAME)
	$(foreach EXTRA_DIR,$(EXTRA_DIRS), cp -R $(EXTRA_DIR) $(CURDIR)/temp/$(PLUGINNAME)/;)

# The dclean target removes compiled python files from plugin directory
# also deletes any .git entry
dclean:
	@echo
	@echo "-----------------------------------"
	@echo "Removing any compiled python files."
	@echo "-----------------------------------"
	find $(HOME)/$(QGISDIR)/python/plugins/$(PLUGINNAME) -iname "*.pyc" -delete
	find $(HOME)/$(QGISDIR)/python/plugins/$(PLUGINNAME) -iname ".git" -prune -exec rm -Rf {} \;


derase:
	@echo
	@echo "-------------------------"
	@echo "Removing deployed plugin."
	@echo "-------------------------"
	rm -Rf $(HOME)/$(QGISDIR)/python/plugins/$(PLUGINNAME)

zip: deploy dclean
	@echo
	@echo "---------------------------"
	@echo "Creating plugin zip bundle."
	@echo "---------------------------"
	# The zip target deploys the plugin and creates a zip file with the deployed
	# content. You can then upload the zip file on http://plugins.qgis.org
	rm -f $(PLUGINNAME).zip
	cd $(HOME)/$(QGISDIR)/python/plugins; zip -9r $(CURDIR)/$(PLUGINNAME).zip $(PLUGINNAME)

package: mock-deploy
	@echo
	@echo "---------------------------"
	@echo "Creating plugin package."
	@echo "---------------------------"
	rm -f $(PLUGINNAME).zip
	cd $(CURDIR)/temp; zip -9r $(CURDIR)/$(PLUGINNAME).zip $(PLUGINNAME)

package-from-git: compile compile-ui
	# Create a zip package of the plugin named $(PLUGINNAME).zip.
	# This requires use of git (your plugin development directory must be a
	# git repository).
	# To use, pass a valid commit or tag as follows:
	#   make package VERSION=Version_0.3.2
	@echo
	@echo "------------------------------------"
	@echo "Exporting plugin to zip package.	"
	@echo "------------------------------------"
	rm -f $(PLUGINNAME).zip
	git archive --prefix=$(PLUGINNAME)/ -o $(PLUGINNAME).zip $(VERSION)
	echo "Created package: $(PLUGINNAME).zip"

clean:
	@echo
	@echo "------------------------------------"
	@echo "Removing uic and rcc generated files"
	@echo "------------------------------------"
	rm $(COMPILED_UI_FILES) $(COMPILED_RESOURCE_FILES)
