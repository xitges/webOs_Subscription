# CD: Render 배포 및 검증

`render.yaml`은 master 브랜치의 GitHub Actions CI가 통과하면 자동 배포하도록 설정한다.
설정 파일 작성만으로 아래 완료 조건이 충족되는 것은 아니다. 실제 서비스 연결과 검증 후 체크한다.

## 1. GitHub 연결 및 최초 배포

1. `.github/workflows/ci.yml`, `render.yaml`, `scripts/check_deployment.py`와 앱 변경 사항을 GitHub 저장소 `xitges/webOs_Suscription`의 master에 반영한다.
2. https://dashboard.render.com 에서 GitHub 계정을 연결하고 해당 저장소 접근을 허용한다.
3. New → Blueprint에서 연결된 GitHub 저장소와 master을 선택하고 루트의 `render.yaml`을 적용한다.
4. 무료 Web Service 설정을 검토하고 배포한다. 기존 서비스가 있다면 중복 생성하지 말고 아래 설정을 적용한다.

| 설정 | 값 |
| --- | --- |
| Runtime | Python |
| Branch | master |
| Build Command | `python -m pip install -r requirements.txt` |
| Start Command | `python -m uvicorn app.master:app --host 0.0.0.0 --port $PORT` |
| Python 환경 변수 | `PYTHON_VERSION=3.13.12` |
| Health Check Path | `/health` |
| Auto-Deploy | After CI Checks Pass |

자동 배포에는 GitHub 계정 연결이 필요하다. Public Git Repository URL만 입력하는 방식은 사용하지 않는다.
별도의 Deploy Hook이나 GitHub 배포 secret은 필요하지 않다.

## 2. master 변경 후 자동 재배포 확인

1. 최초 배포가 Live인지 확인하고 현재 배포 커밋 SHA를 기록한다.
2. 다음 변경을 master에 push 또는 PR merge한다.
3. GitHub Actions의 해당 커밋 CI가 성공하는지 확인한다.
4. 수동 배포 버튼을 누르지 않고 Render에서 자동 배포가 시작되어 Live가 되는지 확인한다.
5. Render의 배포 SHA가 새 master 커밋과 같은지 확인하고 배포 로그 링크를 기록한다.

## 3. 배포 URL 검증

Render가 실제로 발급한 URL로 실행한다. 아래 주소는 예시이며 실제 URL로 바꿔야 한다.

```sh
python scripts/check_deployment.py https://YOUR-SERVICE.onrender.com
```

스크립트는 메인 화면, JS/CSS, health, 모든 구독자의 가전 목록, 모든 가전의 사용량 및 잘못된 ID의 404를 검사한다.
브라우저 동작과 자동 재배포 성공 여부는 이 스크립트만으로 입증되지 않는다.

배포 URL을 브라우저에서 열고 다음을 확인한다.

- 처음 접속하면 5명 구독자 목록이 표시된다.
- 이름/ID/플랜/상태 검색, 상태 필터, 검색과 필터 조합이 작동한다.
- 구독자 선택 시 가전 목록이 바뀌고 가전 검색/상태 필터가 작동한다.
- 가전이 없는 U005 선택 시 빈 목록 안내가 표시된다.
- 가전 선택 시 상세 정보와 Mon~Sun 7일 막대 차트가 표시된다.
- 사용자/가전을 바꿀 때 선택 표시와 상세 정보 및 차트가 갱신된다.
- Active/Online/Normal은 초록, Paused/Standby는 파랑, Expired/Error/Warning은 빨강,
  Offline은 회색, On/Cleaning은 노랑, Off는 연회색 배지로 표시된다.
- 브라우저 콘솔에 오류가 없고 Chart.js CDN 요청이 성공한다.

## 완료 기록

- [ ] Render Web Service를 GitHub 저장소와 연결했다.
- [ ] master에 push/merge하면 CI 성공 후 자동 재배포되는 것을 확인했다.
- [ ] 배포 URL(`.onrender.com`)에서 API 및 위 브라우저 전체 기능을 확인했다.

| 증거 | 실제 값 |
| --- | --- |
| 서비스 URL | 미확인 |
| 최초 배포 커밋 SHA | 미확인 |
| 재배포 커밋 SHA | 미확인 |
| GitHub CI 실행 링크 | 미확인 |
| Render 자동 배포 로그 링크 | 미확인 |
| 배포 URL API 검사 결과 | 미확인 |
| 브라우저 확인 일시 / 확인자 | 미확인 |

공식 참고: [Blueprint 설정](https://render.com/docs/blueprint-spec),
[GitHub CI 연동 자동 배포](https://render.com/docs/deploys),
[FastAPI 배포](https://render.com/docs/deploy-fastapi).
