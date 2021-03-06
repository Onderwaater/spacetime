default:
	@echo "no target given"

tgz:
	git archive master | gzip > spacetime-`cd lib && python -c 'import spacetime.version; print spacetime.version.version'`.tgz

lint:
	sh -c 'export PYTHONPATH="`pwd`/lib:$$PYTHONPATH"; cd pylint; pylint --rcfile pylintrc spacetime'

lintclean:
	rm -f pylint/pylint_*.html

2to3check:
	2to3 lib/spacetime

wininst:
	python win32/geninstaller.py > win32/installer.nsi
	cd win32 && makensis installer.nsi

winpypy:
	python win32/geninstaller.py --pypy > win32/installer-pypy.nsi
	cd win32 && makensis installer-pypy.nsi	

winupgr:
	python win32/geninstaller.py --upgrade > win32/installer-upgrade.nsi
	cd win32 && makensis installer-upgrade.nsi

clean:
	rm -f win32/installer.nsi win32/installer-upgrade.nsi win32/installer-pypy.nsi
