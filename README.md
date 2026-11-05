# EU4ModMaker

Europa Universalis IV 자산 교체 모드를 한글 GUI 로 만든다 — 국기, 이벤트 픽처, 로딩 화면, UI 아이콘, 사운드, 음악, 아이디어 그룹, 로컬라이제이션.

## 실행

- 소스에서: `run.bat` 또는 `python main.py` (Python 3.13, `pip install -r requirements.txt`)
- 단일 exe: `build_exe.bat` 이 `<out 루트>\eu4_flag_modder\dist\EU4ModMaker.exe` 를 만든다 (out 루트는 D:\out, D: 가 없으면 C:\dev\out)
- 게임 폴더 기본값은 `C:\Program Files (x86)\Steam\steamapps\common\Europa Universalis IV`, 모드 설치 폴더 기본값은 문서 폴더의 Paradox Interactive\Europa Universalis IV\mod

## 테스트

- `python -m pytest tests -q` — src 모듈만 검사하고 GUI 는 띄우지 않는다
- 국가 태그 표(`src/countries.py`)는 게임이 설치돼 있으면 `common/country_tags/00_countries.txt` 와 대조한다

## 구조

```
main.py            Tk GUI
src/               모드 산출 모듈 (국가·이벤트 픽처·로딩 화면·아이콘·사운드·음악·아이디어·로컬·빌더)
tests/             pytest
EU4ModMaker.spec   PyInstaller 설정
```
