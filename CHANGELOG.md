# CHANGELOG

All notable changes to this project will be documented in this file. Versioning on the form Major.Minor.Patch (semantic versioning-like), where:

- Major: Changes that break current functionality (e.g. change command names or change argument order)
- Minor: New features that adds functionality but doesn't break any old functionality (e.g. adding new words to noun and adjective lists or change the look of the Teamo messages)
- Patch: Fixes (e.g. bug fixes or backend fixes)

Changes should be in one of the following categories:
- New
- Changes
- Fixes


---
## 1.0.0 - (2020-09-13)

### New
* Initial release


---
## 1.1.0 - (2020-09-16)

### Changes
* Adds an activity ("Listening to @Teamo help")

### Fixes
* Fixes a bug which wouldn't let Teamo receive commands from new servers


---
## 1.2.0 - (2020-09-17)

### Changes
* Correctly links to the new Teamo repository (moved from hassanbot to gris-martin)

### Fixes
* Makes sure you can't set an invalid timezone with the `settings set timezone <timezone>` command
* Fixes a few timezone and resource issues that broke most commands
