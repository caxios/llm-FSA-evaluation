# arXiv · SSRN 제출 안내

## 준비된 파일

| 용도 | 파일 |
|---|---|
| arXiv 업로드용 소스 | `release/arxiv/arxiv_source.tar.gz` (main.tex, main.bbl, references.bib, 그림 5개; pdflatex만으로 컴파일 확인) |
| arXiv 입력 정보 | `release/arxiv/arxiv_metadata.md` (제목, 분류, 코멘트, 초록) |
| 미리보기 PDF | `release/arxiv/main_preview.pdf` |
| SSRN 업로드용 PDF | `release/ssrn/Park_2026_LLM_Valuation_Filing_Fidelity.pdf` (11쪽) |
| SSRN 입력 정보 | `release/ssrn/ssrn_metadata.md` (키워드, JEL 코드, 추천 분야, 초록) |
| 초록 (일반 텍스트) | `release/abstract.txt` (1,854자; arXiv 제한 1,920자) |
| 재현 데이터 패키지 | `release/replication_data.zip` (39 MB; GitHub Release·Zenodo 업로드용) |
| 논문 원본 | `paper/main.tex`, `paper/references.bib`, `paper/figures/` |
| 저장소 공개 파일 | `LICENSE`(MIT), `DATA_LICENSE.md`, `CITATION.cff`, `docs/reproduce.md`, `README.md` |

## 제출 전에 꼭 하실 일

1. **PDF를 끝까지 읽고 확인하기.** 저자 표기, 숫자, 해석, 한계를 확인하세요. 원고는 AI 보조로 작성했으므로 최종 책임은 저자에게 있습니다. 논문 말미의 "Use of AI tools" 문단에도 그렇게 밝혀 두었습니다.
2. **저자 이름 순서.** 서양식 순서인 "Dong Gyu Park"으로 적었습니다. "Park Dong Gyu"나 "Donggyu Park" 등으로 바꾸려면 다음 세 곳을 같이 고치고, 재빌드 명령을 실행하세요.
   - `paper/main.tex`의 `\author`
   - `CITATION.cff`
   - 메타데이터 파일 2개
3. **GitHub 저장소 공개.** 논문에 `https://github.com/caxios/llm-FSA-evaluation`을 코드·데이터 위치로 적었습니다.
   - 저장소를 공개(Public)로 바꾸고, 로컬 커밋과 태그를 푸시하세요: `git push origin main --tags`
   - 저장소를 공개하지 않으려면 논문의 "Data, code and preregistration" 문단을 "available from the author upon request"로 고치세요.
4. **재현 데이터 올리기(선택).** `release/replication_data.zip`을 GitHub Release나 Zenodo에 올리세요. Zenodo에 올리면 DOI가 생겨 인용하기 좋습니다.
5. **이용약관 확인.** 다음 세 가지 조건에 맞는지 직접 확인하세요.
   - Google Gemini API 약관상 모델 출력의 공개 가능 여부
   - OpenDART 데이터의 출처 표시 조건
   - KRX 데이터는 재배포하지 않도록 이미 빼 두었습니다.
6. **참고문헌.** arXiv 페이지에서 모든 문헌의 제목과 저자를 확인했습니다. 프로젝트 문서에만 있던 Garcia(SSRN) 문헌은 실재를 확인하지 못해 뺐습니다.

## arXiv 제출 순서

1. https://arxiv.org 에서 계정을 만들고 로그인합니다. 학교·기관 이메일이 없으면 개인 이메일로도 가입할 수 있습니다.
2. **추천(endorsement) 확인.** 처음 제출하는 분야(q-fin)는 기존 저자의 추천이 필요할 수 있습니다.
   - 제출 과정에서 추천이 필요하다고 나오면, 안내되는 추천 코드를 해당 분야의 기존 arXiv 저자에게 보내 추천을 받으세요.
   - 소속이 없는 독립 연구자는 대개 추천이 필요합니다.
3. "Submit" → "Start new submission"을 누릅니다.
   - License: CC BY 4.0 (권장)
   - Primary category: **q-fin.GN**, cross-list: **cs.CL, cs.AI**
4. "Upload files"에서 `arxiv_source.tar.gz`를 올립니다. arXiv가 자동 컴파일하니, 미리보기 PDF가 `main_preview.pdf`와 같은지 확인하세요.
5. Metadata 입력: `arxiv_metadata.md`의 제목, 저자, 코멘트, 초록을 복사해 넣습니다. 초록은 `release/abstract.txt` 그대로 쓰면 됩니다.
6. 제출합니다. 보통 다음 영업일에 공개되고, 그 전에 관리자 검토가 있습니다.

## SSRN 제출 순서

1. https://www.ssrn.com 에서 계정을 만듭니다. 무료이고 소속 없이도 가입할 수 있습니다.
2. "Submit a Paper"를 누릅니다.
3. PDF를 올립니다: `Park_2026_LLM_Valuation_Filing_Fidelity.pdf`
4. `ssrn_metadata.md`에서 다음 항목을 복사해 넣습니다.
   - 제목, 초록, 키워드
   - JEL 코드: G12, G14, C45, M41
   - Date written
   - 분류 네트워크: FEN의 Asset Pricing & Valuation 계열, ARN 등
5. arXiv에 먼저 올렸다면 "Related links"에 arXiv 주소를 넣습니다.
6. 제출하면 SSRN 검토 후 며칠 안에 공개됩니다.

## 원고를 고친 뒤 다시 만드는 방법

```bash
.venv/Scripts/python scripts/build_paper_figures.py      # 그림 (제목 없는 논문용)
cd paper && latexmk -pdf main.tex && cd ..              # PDF
# arXiv 패키지와 SSRN PDF 갱신
cp paper/main.tex paper/main.bbl paper/references.bib release/arxiv/src/
cp paper/figures/F2_beta_by_group.pdf paper/figures/F3_decomposition.pdf paper/figures/F4_memory_scatter.pdf paper/figures/F6_stages.pdf paper/figures/F8_pooled.pdf release/arxiv/src/figures/
(cd release/arxiv/src && tar -czf ../arxiv_source.tar.gz main.tex main.bbl references.bib figures)
cp paper/main.pdf release/ssrn/Park_2026_LLM_Valuation_Filing_Fidelity.pdf
.venv/Scripts/python scripts/build_release.py           # 재현 데이터 패키지
```
