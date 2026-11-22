# Changelog

## [0.4.0](https://github.com/Vibrant-Planet-Open-Science/fvs2py/compare/v0.3.1...v0.4.0) (2026-11-22)


### ⚠ BREAKING CHANGES

* `lib_path` is now keyword-only, so `FVS("/path/to/FVSpn.so")` becomes `FVS(lib_path="/path/to/FVSpn.so")`.

### Features

* adds --version and --build-info to the fvs command ([#91](https://github.com/Vibrant-Planet-Open-Science/fvs2py/issues/91)) ([402de6c](https://github.com/Vibrant-Planet-Open-Science/fvs2py/commit/402de6c0efd037072fd459085bfb28f4e449627a))
* loads FVS libraries from fvs-runtime by variant ([af40af5](https://github.com/Vibrant-Planet-Open-Science/fvs2py/commit/af40af59f636ed6c6f46541e3cca3a04f9ac4fe6))
* reports floating-point faults raised by FVS ([#92](https://github.com/Vibrant-Planet-Open-Science/fvs2py/issues/92)) ([1a72962](https://github.com/Vibrant-Planet-Open-Science/fvs2py/commit/1a72962015b16dfeb08d9c7faa083fe6f8f246e3))


### Bug Fixes

* reads all 22 FVS summary values, ending a buffer overflow ([#88](https://github.com/Vibrant-Planet-Open-Science/fvs2py/issues/88)) ([02e2a54](https://github.com/Vibrant-Planet-Open-Science/fvs2py/commit/02e2a54ec9bd08381f75f9b9a6bf5b327691e36c))


### Documentation

* re-runs the example notebook with FVS 2027.1.1 ([#90](https://github.com/Vibrant-Planet-Open-Science/fvs2py/issues/90)) ([67c170a](https://github.com/Vibrant-Planet-Open-Science/fvs2py/commit/67c170a90d5c20a66aea9d369a87c30ca08cd453))

## [0.3.1](https://github.com/Vibrant-Planet-Open-Science/fvs2py/compare/v0.3.0...v0.3.1) (2026-11-22)


### Features

* adds FVS.version and FVS.build_info ([#82](https://github.com/Vibrant-Planet-Open-Science/fvs2py/issues/82)) ([3a162b8](https://github.com/Vibrant-Planet-Open-Science/fvs2py/commit/3a162b83df56fc6b0beb80a165607bafdae94e49))
* reads FVS output tables in memory ([#84](https://github.com/Vibrant-Planet-Open-Science/fvs2py/issues/84)) ([794d2e9](https://github.com/Vibrant-Planet-Open-Science/fvs2py/commit/794d2e96deccd8853e6ee0eccfc93965c8785f92))

## [0.3.0](https://github.com/Vibrant-Planet-Open-Science/fvs2py/compare/v0.2.2...v0.3.0) (2026-11-18)


### ⚠ BREAKING CHANGES

* opening a new FVS instance in the same Python process now closes an existing one if it is idle and raises if it is mid-run.

### Features

* allows one open FVS instance per process ([#80](https://github.com/Vibrant-Planet-Open-Science/fvs2py/issues/80)) ([c322dc3](https://github.com/Vibrant-Planet-Open-Science/fvs2py/commit/c322dc33447d0ccb0ffc76f2fd451d32a5f32d2d))

## [0.2.2](https://github.com/Vibrant-Planet-Open-Science/fvs2py/compare/v0.2.1...v0.2.2) (2026-11-17)


### Features

* returns enum members from FVS status and stop point codes ([#78](https://github.com/Vibrant-Planet-Open-Science/fvs2py/issues/78)) ([d3aec83](https://github.com/Vibrant-Planet-Open-Science/fvs2py/commit/d3aec83f2abca2c89447c13c2a8c87777bfe38af))


### Bug Fixes

* adds restart code 7 to FvsRestartCode ([#77](https://github.com/Vibrant-Planet-Open-Science/fvs2py/issues/77)) ([2da8122](https://github.com/Vibrant-Planet-Open-Science/fvs2py/commit/2da81221e0c130dc5ef7b5067c87693f3e374a6a))
* bases the not-started guard on FVS return codes ([#76](https://github.com/Vibrant-Planet-Open-Science/fvs2py/issues/76)) ([fa1ae69](https://github.com/Vibrant-Planet-Open-Science/fvs2py/commit/fa1ae6935140a4c8c92229caa8abb35b88703d78))
* replaces attribute dispatchers with AttributeTable and stops buffer aliasing ([#72](https://github.com/Vibrant-Planet-Open-Science/fvs2py/issues/72)) ([1082dd6](https://github.com/Vibrant-Planet-Open-Science/fvs2py/commit/1082dd6051bec00ce5d14c895b3b0a1896a1c846))


### Documentation

* adds CONTRIBUTING.md with dev setup, issue, style, and commit guidelines ([#67](https://github.com/Vibrant-Planet-Open-Science/fvs2py/issues/67)) ([bbcc3cc](https://github.com/Vibrant-Planet-Open-Science/fvs2py/commit/bbcc3ccd1f309b71f8cdae2b8374c9902f6cd5ec))
* reworks the demo notebook with a steering example and corrects stop_point_year docs ([#79](https://github.com/Vibrant-Planet-Open-Science/fvs2py/issues/79)) ([21e34fb](https://github.com/Vibrant-Planet-Open-Science/fvs2py/commit/21e34fba557660927efdf1a8ddc8d81af19a133c))


### Code Refactoring

* moves the library-loaded guard into _invoke ([#71](https://github.com/Vibrant-Planet-Open-Science/fvs2py/issues/71)) ([911c809](https://github.com/Vibrant-Planet-Open-Science/fvs2py/commit/911c8093b9e0436037f9dc08f83603fd89f9e4cf))
* replaces mixins with a thin FVS facade over FvsCore ([#75](https://github.com/Vibrant-Planet-Open-Science/fvs2py/issues/75)) ([a8041a0](https://github.com/Vibrant-Planet-Open-Science/fvs2py/commit/a8041a0cbfd2c24763e510ae09593206201121a0))
* simplifies the simulation lifecycle ([#74](https://github.com/Vibrant-Planet-Open-Science/fvs2py/issues/74)) ([f94a5a5](https://github.com/Vibrant-Planet-Open-Science/fvs2py/commit/f94a5a58c74132fba58f26ab5a63e3e90d2168cc))
* tightens the routine registry ([#73](https://github.com/Vibrant-Planet-Open-Science/fvs2py/issues/73)) ([8c2e8aa](https://github.com/Vibrant-Planet-Open-Science/fvs2py/commit/8c2e8aae17f59a15240229285d674a79b6ac9e0d))

## [0.2.1](https://github.com/Vibrant-Planet-Open-Science/fvs2py/compare/v0.2.0...v0.2.1) (2026-11-09)


### Features

* adds fvs CLI entry point ([#57](https://github.com/Vibrant-Planet-Open-Science/fvs2py/issues/57)) ([2102810](https://github.com/Vibrant-Planet-Open-Science/fvs2py/commit/2102810fd23c0171adc5818eead54bc6c7111d01))


### Documentation

* converts reST docstring markup to single backticks ([#60](https://github.com/Vibrant-Planet-Open-Science/fvs2py/issues/60)) ([0ff367b](https://github.com/Vibrant-Planet-Open-Science/fvs2py/commit/0ff367b2713fb6c93b297a9ca54378814ca22726))
* fixes run_batch loop example that never ends after an FVS error ([#63](https://github.com/Vibrant-Planet-Open-Science/fvs2py/issues/63)) ([4cb12f2](https://github.com/Vibrant-Planet-Open-Science/fvs2py/commit/4cb12f2493513f327fcf155dcc4a62327c56767f))


### Build System

* adds PyPI package metadata ([#59](https://github.com/Vibrant-Planet-Open-Science/fvs2py/issues/59)) ([016dd39](https://github.com/Vibrant-Planet-Open-Science/fvs2py/commit/016dd395106c20819dfadbfee68bda55837762d1))

## [0.2.0](https://github.com/Vibrant-Planet-Open-Science/fvs2py/compare/v0.1.1...v0.2.0) (2026-09-01)


### ⚠ BREAKING CHANGES

* relicenses fvs2py under the MIT License ([#48](https://github.com/Vibrant-Planet-Open-Science/fvs2py/issues/48))

### Features

* relicenses fvs2py under the MIT License ([#48](https://github.com/Vibrant-Planet-Open-Science/fvs2py/issues/48)) ([635a13c](https://github.com/Vibrant-Planet-Open-Science/fvs2py/commit/635a13c4337f3068955ef0f8ed629428060644c5))

## [0.1.1](https://github.com/Vibrant-Planet-Open-Science/fvs2py/compare/v0.1.0...v0.1.1) (2026-07-29)


### Bug Fixes

* enables DLL unload on Windows ([#46](https://github.com/Vibrant-Planet-Open-Science/fvs2py/issues/46)) ([7d77551](https://github.com/Vibrant-Planet-Open-Science/fvs2py/commit/7d7755103da0ee4e753c7fb4b052a075c9219837))
