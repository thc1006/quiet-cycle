# Quiet Cycle 0.3.0

可直接嵌入其他程式的 Python 函式庫。沒有前端、帳號、資料庫或雲端推論。
本版新增真正可訓練的多因素模型，不再只把穿戴資料匯入後擱置不用。

**它尚未經真人資料的臨床效能驗證，沒有附上真人訓練權重，也不是已證明全球最準的模型。**
隨附資料與訓練範例全為合成測試；不能把範例權重直接用於患者。

[完整 README 與實作公式](README.md) · [研究依據與邊界](docs/EVIDENCE_REVIEW.md) ·
[訓練流程](docs/TRAINING.md) · [實测報告](docs/TEST_REPORT.md)

## 執行與嵌入

```sh
python -m pip install .
python examples/train_multifactor.py --output /tmp/quiet-cycle-example
quiet-cycle forecast /tmp/quiet-cycle-example/request.json --model /tmp/quiet-cycle-example/model.json
```

```python
from pathlib import Path
from quietcycle import PipelineRequest
from quietcycle.learning import FittedModel, MultiFactorPipeline
from quietcycle.serialization import loads

folder = Path("/tmp/quiet-cycle-example")
model = FittedModel.model_validate(loads((folder / "model.json").read_text()))
request = PipelineRequest.model_validate(loads((folder / "request.json").read_text()))
result = MultiFactorPipeline(model).run(request.dataset, request.query)
print(result.status, result.point_date)
```

套件未發布到 PyPI；從本 repo 或附帶 wheel 安裝。Python 3.11 以上，核心只依賴
Pydantic。FastAPI/Uvicorn 是選配，NumPy 只用於獨立驗算測試。

## 演算法

個人歷史中位數作為基線 $b_i$，模型學習未來週期長度的偏差 $r_i=L_i-b_i$。

$$
\hat\beta=\arg\min_\beta\sum_{i\in\mathrm{train}}(r_i-x_i^\top\beta)^2
+\lambda\sum_{j=1}^{p-1}\beta_j^2,
\qquad (X^\top X+\lambda D)\hat\beta=X^\top r.
$$

所有標準化參數只由 training 決定。症狀與穿戴候選的權重由資料學得，tuning
選擇模型及向個人歷史縮減的比例，calibration 不參與選模，test 完全保留。

$$
a=\operatorname{clip}\left(\frac{\sum g_i(L_i-b_i)}{\sum g_i^2},0,1\right),\qquad
\widehat L_i=\max(d,\lfloor b_i+a g_i+1/2\rfloor).
$$

校準殘差 $e_i=|L_i-\widehat L_i|$，分位數順位：

$$
k=\lceil(n+1)(1-\alpha)\rceil,\qquad q=e_{(k)}.
$$

若 $k>n$，必須回傳無界區間，不可偷用樣本最大值。這個公式的覆蓋率解釋有
可交換性等條件；不代表每位使用者或任意分布變化下都保證九成命中。

英文 README 進一步列出時間可見性、量測日彙整、缺失處理、量化、矩陣解法、
選模、區間與貢獻分解公式，並對應實作函式。

## 已接通的資料

沿用 JSON、JSONL、CSV、Python mapping rows、限定的 FHIR R4 Observation。
量測先正規化單位，再進入因果時間截面；腕溫、皮膚溫度、體溫及不同 HRV 指標不混用。
症狀未填不等於沒有症狀，補登不會出現在更早的重播中。

預設特徵為經期歷史、頭痛、疲倦、腹部疼痛、腸胃狀況、腕溫、靜息心率、RMSSD
與睡眠；可配置症狀及量測項目。原始裝置降噪、所有醫療情境與疾病推論並未包含。

**預設模型在開始後經過 20 天（週期第 21 天）預測。** 它不是任何日期都能使用的同一個
模型，也不是排卵預測器。其他時間點需配置、訓練及驗證獨立模型；不能用第 21 天的
表現宣称第一天就同樣準確。另需明確確認昨日以前尚未出現下一次經期。

## 檢查與限制

以精確分數求解正常方程，返回前再次檢查方程完全成立；這證明計算沒有殘差，
不證明人體沒有誤差。合成壓力測試保留有訊號、無訊號與關係反轉三種結果，包含
模型比基線差的情形。實際測試數字與未執行項目見 TEST_REPORT，不能用全綠取代臨床資料。

所有人可以 fork、修改、替換模型或嵌入底層。更改特徵、模型或資料來源後要修改版本，
重新校準並保留獨立測試。模型 JSON 與雜湊 ID 仍可能洩露敏感資訊，不是匿名資料。
授權 MIT；沒有公開發布、部署或上傳任何私人健康資料。
