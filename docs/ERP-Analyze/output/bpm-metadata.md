# BPM（華苓 Agentflow / EFGP）測試站 Metadata 與關聯分析

> 產出日期：2026-06-22　|　資料來源：MS SQL Server `EFGP`（10.200.206.222:1433）　|　帳號：`sa`（**本任務全程唯讀，只下 SELECT**）

> 本文件由 agent 依 [docs/analyze-bpm-metadata.md](../analyze-bpm-metadata.md) 指令自動產出，全程僅執行 `SELECT`（連線 autocommit、未開交易、無任何寫入）。


## 0. 重要前提與資料來源

| 項目 | 說明 |
| --- | --- |
| 資料庫 | `EFGP`（MS SQL Server，連線 10.200.206.222:1433）|
| 系統類型 | 華苓 **Agentflow BPM**（企業流程管理 / 簽核表單平台） |
| 權限限制 | 帳號 `sa` 具完整權限，但本任務**全程唯讀**；列數取自 `sys.dm_db_partition_stats`（堆積/叢集索引 `index_id IN (0,1)` 之 `row_count` 加總，屬**估計值**，非即時 `COUNT(*)`）。|
| 中文名來源 | 本庫**無** `MS_Description` 擴充屬性，表/欄位皆為英文命名；中文名欄位以英文原名呈現（已於已知條件驗證標註）。 |
| 統計摘要 | 表 617 張（有資料 286）、欄位 7,417 個、估計總列數 12,452,532；表級中文名 0、欄位級中文名 0。|

> ⚠️ 區分事實與推導：標示「**估計值**」者來自 `dm_db_partition_stats` 統計；標示「**推導/推測**」者為依命名慣例推斷（本庫無實體外鍵），非實際查得。


## 1. 總覽：領域分群與資料量

下表以表名前 3 字元分群（前綴），列數為各群 `dm_db_partition_stats` 估計值加總，取前 30 群。

| 前綴 | 領域（推測） | 表數 | 有資料表數 | 估計列數 |
| --- | --- | ---: | ---: | ---: |
| `Cha` | 簽核/變更 | 17 | 4 | 3,874,335 |
| `Wor` | 工作流(Workflow) | 8 | 5 | 1,536,684 |
| `Par` | — | 5 | 3 | 1,386,860 |
| `Tra` | — | 3 | 3 | 1,265,346 |
| `Act` | 活動(Activity) | 5 | 4 | 944,231 |
| `Pro` | 流程(Process) | 25 | 16 | 560,752 |
| `Loc` | — | 3 | 3 | 447,822 |
| `Not` | — | 1 | 1 | 417,405 |
| `For` | 表單(Form) | 19 | 15 | 254,828 |
| `Str` | — | 3 | 2 | 236,215 |
| `IAp` | — | 1 | 1 | 210,297 |
| `dfs` | 自訂(df) | 11 | 11 | 185,300 |
| `Lic` | — | 2 | 2 | 148,720 |
| `Rel` | — | 3 | 1 | 133,235 |
| `App` | — | 2 | 2 | 116,747 |
| `Bou` | — | 1 | 1 | 105,641 |
| `Too` | — | 1 | 1 | 95,031 |
| `Blo` | — | 2 | 2 | 92,805 |
| `OJB` | — | 10 | 4 | 70,941 |
| `DBR` | — | 1 | 1 | 61,651 |
| `Imp` | — | 1 | 1 | 51,804 |
| `dfp` | — | 3 | 3 | 47,175 |
| `Cus` | — | 4 | 1 | 46,303 |
| `Dec` | — | 11 | 4 | 31,215 |
| `NoC` | — | 2 | 1 | 17,917 |
| `Doc` | 文件(Document) | 22 | 5 | 17,910 |
| `SYN` | 同步/整合 | 33 | 8 | 12,231 |
| `Bam` | — | 6 | 4 | 10,028 |
| `Con` | — | 3 | 2 | 9,325 |
| `Fun` | — | 3 | 3 | 8,547 |

> 共 168 個前綴群；完整表清單見第 4 節，欄位見第 5 節。


## 2. 已知條件驗證

| # | 已知條件 | 驗證方法 | 結論 |
| --- | --- | --- | --- |
| 1 | 資料主要落在 `dbo` schema | 以 `sys.schemas`+`sys.tables` 統計各 schema 表數 | **成立**。全部 617 張使用者表皆屬 `dbo`，無其他自訂 schema 含業務資料。|
| 2 | 表名有命名前綴規律 | 依前 3 字元分群 | **成立（推導）**。可見明顯前綴族：`EPM`(企業流程)、`ISO`(文件)、`Pro`/`Doc`/`For`(流程/文件/表單)、`SYN`(同步)、`Org`/`Per`(組織/權限) 等；前綴含義為依命名推導。|
| 3 | 中文名來源（MS_Description / 應用字典 / 欄位名） | 查 `sys.extended_properties`、`MLANGUAGE`、`*Definition` 表 | **分層修正**：schema 層 `MS_Description` 為 **0 筆**（欄位名無中文）；但**業務語意層有繁體中文**，存於資料列——`ProcessDefinition`/`FormDefinition` 的流程/表單名、`MLANGUAGE`(zh_TW) 的 UI 標籤。詳見第 3.2 節。|
| 4 | 是否有實體外鍵 | 查 `sys.foreign_keys` | **無任何實體 FK（0 筆）**。關聯改以**命名慣例推導**：`XxxId` 欄位對應主鍵為 `XxxId` 的表 `Xxx`。|

## 3. 關聯模型

- **實體外鍵（FK）**：經 `sys.foreign_keys` 驗證為 **0 筆**（事實）。
- **隱含關聯（推導，中可信度）**：以「單欄主鍵名稱唯一」的表作為被參照端（共 11 個可辨識主鍵），其他表若含同名欄位即視為隱含 FK，推導出 **26 條**關聯。已排除泛用欄位（ID/OID/CODE/TenantId…）以降低誤判。
- 下表列出被其他表參照最多的前 30 個核心表（被參照次數＝入度）。

| 核心表 | 中文名 | 被參照次數 | 估計列數 |
| --- | --- | ---: | ---: |
| `SYN_ISODocCmItem` |  | 18 | 0 |
| `SYN_ExtFuncDef` |  | 3 | 0 |
| `CriticalPriority` |  | 2 | 2 |
| `JMS_USERS` |  | 1 | 5 |
| `JMS_TRANSACTIONS` |  | 1 | 0 |
| `CriticalDefinition` |  | 1 | 2 |

### 3.1 共用鍵欄位（跨表關聯樞紐，推導）

下列欄位以同名出現在多張表，且形態為鍵（非稽核欄位）。在無實體 FK 的系統中，這些是實際的跨表 join 樞紐（取前 30）。

| 欄位名 | 出現表數 | 代表表（取樣） |
| --- | ---: | --- |
| `OID` | 509 | `AbsenceRecord`, `AccessRightEntity`, `ActivityDefinition`, `ActivityDefinitionEntity`, `ActivityNotification`, `ActivitySetDefinition`… |
| `formSerialNumber` | 102 | `ChatFileExecutionRecord`, `ChatFileExperienceRecords`, `EBGForm`, `EBGForm_templateGrid`, `EBGHistoricalSigner`, `EPM_BudgetCreateForm`… |
| `id` | 84 | `ActivityDefinition`, `ActivityDefinitionEntity`, `ActivitySetDefinition`, `AllUserUnit`, `AnalyzedService`, `AnalyzedServiceParameter`… |
| `containerOID` | 83 | `AccessRightEntity`, `ActivityDefinition`, `ActivityDefinitionEntity`, `ActivitySetDefinition`, `ActualParameter`, `AnalyzedServiceParameter`… |
| `processSerialNumber` | 81 | `AdapterDingtalkTodoTask`, `AppFormActivityRecord`, `ChatFileExperienceRecords`, `ChatFileQARecord`, `ChatFileTransferRecords`, `EBGForm`… |
| `userOID` | 32 | `AdapterDingtalkTodoTask`, `AdapterUser`, `ArchiveProcessInReduction`, `AssignmentNoPerPerson`, `ChatFileUserManagement`, `ConnectedUserInfo`… |
| `userId` | 23 | `ArchiveEventRecord`, `BamWorkAssignmentData`, `BamWorkItemData`, `ChatFileQARecord`, `ConnectedUserInfo`, `EBGHistoricalSigner`… |
| `oid` | 23 | `MLANGUAGE`, `MLANGUAGE_RELATION`, `ecp_anc_info`, `ecp_anc_range`, `ecp_anc_type`, `ecp_anc_type_range`… |
| `docNo` | 19 | `ChatFileISOTransferRecords`, `ChatFileKnowledge`, `DocDraft`, `DocNoReserved`, `Documents`, `ISOFileReadingRecord`… |
| `orgId` | 18 | `EBGPropertise`, `SYN_Employee`, `SYN_ExtOrg`, `SYN_FunctionDefinition`, `SYN_FunctionLevel`, `SYN_Functions`… |
| `ownerOID` | 17 | `AbsenceRecord`, `AccessRightEntity`, `ArchiveExcludedProcess`, `ArchiveProcessRule`, `AuthorityScopeSlot`, `CuzPatternDefinition`… |
| `processInstanceOID` | 14 | `BamActInstData`, `BamProInstData`, `BamWorkAssignmentData`, `BamWorkItemData`, `CriticalMessageLog`, `NoCmDocument`… |
| `processDefinitionId` | 13 | `BamProcessRecord`, `BamSetting`, `ChatFileAssistedReading`, `ChatFileExperience`, `ChatFileExperienceRecords`, `ChatFileQARecord`… |
| `organizationOID` | 12 | `AdapterConfig`, `Employee`, `FunctionDefinition`, `FunctionLevel`, `Groups`, `OrganizationUnit`… |
| `processId` | 12 | `ArchiveExcludedProcess`, `BamActInstData`, `BamProInstData`, `BamWorkAssignmentData`, `BamWorkItemData`, `BpmActivityMappingDocProp`… |
| `serialNumber` | 11 | `ArchiveProcessDetail`, `BamProInstData`, `BamProcessRecord`, `BamWorkAssignmentData`, `CriticalMessageLog`, `FormDataObject`… |
| `categoryOID` | 11 | `CmItemAcsRight`, `DefCmItem`, `DesignTempFile`, `FormCategoryAccessRight`, `FormDefinitionCmItem`, `LayoutCmItem`… |
| `unitId` | 10 | `AuthorityUnits`, `SYN_ExtPartJob`, `SYN_ExtUser`, `SYN_Functions`, `SYN_Role`, `SYN_Title`… |
| `documentOID` | 10 | `DeployDocServer`, `DeployedUnit`, `ISOCloudApplyDocsRecord`, `ISOFile`, `ISOFileReadingRecord`, `ISOPortabilityRecord`… |
| `workItemOID` | 10 | `AdapterDingtalkTodoTask`, `BamWorkAssignmentData`, `BamWorkItemData`, `LocalNoticeWorkItem`, `LocalToDoWorkItem`, `Server2NoticeWorkItem`… |
| `creator_id` | 10 | `ecp_anc_info`, `ecp_chart`, `ecp_link`, `ecp_page_basic`, `ecp_page_module`, `ecp_product`… |
| `costCenterCode` | 10 | `EPM_CostCenter`, `EPM_CostCenterCategory`, `EPM_CostCenterDept`, `EPM_ExpenseForm`, `EPM_ExpenseForm_CM`, `EPM_PrepaidExpenseForm`… |
| `applicantDeptId` | 10 | `EPM_BudgetCreateForm`, `EPM_BudgetDivertForm`, `EPM_BudgetReviseForm`, `EPM_ExpenseForm`, `EPM_ExpenseForm_CM`, `EPM_PrepaidExpenseForm`… |
| `applicantERPDeptId` | 10 | `EPM_BudgetCreateForm`, `EPM_BudgetDivertForm`, `EPM_BudgetReviseForm`, `EPM_ExpenseForm`, `EPM_ExpenseForm_CM`, `EPM_PrepaidExpenseForm`… |
| `definitionOID` | 9 | `AttachmentInstance`, `Draft`, `FormDataObject`, `FormInstance`, `FormInstance_BAK1212`, `Functions`… |
| `externalReferenceOID` | 8 | `MailApplication`, `ParticipantDefinition`, `ParticipantDefinition2`, `RestfulApplication`, `ScriptingApplication`, `SessionBeanApplication`… |
| `formId` | 8 | `FormColumnMask`, `FormDesignAssistant`, `MobileDynamicFormRecord`, `MultiProcessRefRecord`, `SqlAllowedForm`, `SysTiptopMappingKey`… |
| `organizationId` | 8 | `CmItemAcsRight`, `FormCategoryAccessRight`, `OrgWizardAuthorityScope`, `PackageCategoryAccessRight`, `ParticipantDefinition`, `ParticipantDefinition2`… |
| `mainProcessId` | 8 | `BamActInstData`, `BamProInstData`, `BamWorkAssignmentData`, `BamWorkItemData`, `WrapBamActInstData`, `WrapBamProInstData`… |
| `mainProcessInstanceOID` | 8 | `BamActInstData`, `BamProInstData`, `BamWorkAssignmentData`, `BamWorkItemData`, `WrapBamActInstData`, `WrapBamProInstData`… |

### 3.2 流程／表單繁中對照（業務語意層）

Agentflow 將中文存為**資料**而非 schema 註解。資料表中的 `processSerialNumber` = `processDefinitionId` + 流水號，可接回定義表取得中文業務名；`formSerialNumber` 同理對應表單定義。

**Join 食譜：**

```sql
-- 任一資料表的 processSerialNumber → 中文流程名
SELECT d.processSerialNumber,
       pi.processDefinitionId,
       pd.processDefinitionName  AS 中文流程名
FROM   <任一含 processSerialNumber 的表> d
JOIN   ProcessInstance   pi ON pi.serialNumber = d.processSerialNumber
JOIN   ProcessDefinition pd ON pd.id = pi.processDefinitionId;  -- 或直接以 processDefinitionId 前綴比對
```


**流程定義對照表（processDefinitionId → 中文名，共 113 個定義，依流程實例數排序）**

| processDefinitionId（serialNumber 前綴） | 中文流程名 | 流程實例數 |
| --- | --- | ---: |
| `DFSALE` | 銷貨申請單 | 54,853 |
| `APPFORMPROCESSPKG_ESSF07` | 請假單 | 29,769 |
| `APPFORMPROCESSPKG_ESSF03` | 補刷卡申請單 | 18,977 |
| `dfpurchase` | 請購(修)申請單 | 16,036 |
| `dfsuggest` | 簽呈 | 7,070 |
| `dfsale_b` | 業務處銷貨申請單 | 5,505 |
| `APPFORMPROCESSPKG_ESSF04` | 加班申請單 | 4,368 |
| `APPFORMPROCESSPKG_ESSF20` | 出差申請單 | 3,301 |
| `APPFORMPROCESSPKG_ESSF21` | 出差登記單 | 1,765 |
| `dfgovernment` | 內部聯絡單 | 1,574 |
| `cgsuggest` | 酷綠公司簽呈(Ver.16) | 1,525 |
| `APPFORMPROCESSPKG_ESSF06` | 加班補休申請單 | 1,471 |
| `dftake` | 物品領用單 | 1,350 |
| `APPFORMPROCESSPKG_ESSF50` | 班次變更申請單 | 782 |
| `dfexpense` | 出差旅費報支單 | 325 |
| `TIPTOPPROCESSPKG_aapt120` | 雜項應付款項請款作業 | 287 |
| `dfbasedata` | 基礎資料異動申請單 | 266 |
| `dfwaorder` | 加盟物品訂購單 | 217 |
| `dfsuggest_tradefinancial` | 財務簽呈﹝國貿﹞ | 185 |
| `dfCRMBankInfo` | CRM銀行資料新增/修改申請單 | 169 |
| `APPFORMPROCESSPKG_ESSF17` | 銷假申請單 | 155 |
| `dfcreditevl` | 新增客戶信用額度評估表(Ver.15)(Ver.23) | 140 |
| `TIPTOPPROCESSPKG_afat102` | 資產部門移轉作業 | 139 |
| `dfrequest` | 需求單 | 93 |
| `dfsuggest_tradechinapay` | 大陸出款簽呈﹝國貿﹞ | 83 |
| `dffailproduct` | 不合格品處置單 | 72 |
| `TIPTOPPROCESSPKG_apmt540` | 採購單維護作業 | 70 |
| `PKG17477967136071` | 檔案變更申請單 | 68 |
| `dfResignation` | 離職申請單 | 67 |
| `PKG16062700543641` | 委外檢測申請單 | 56 |
| `dfcomplaint` | 客戶抱怨處理單 | 48 |
| `dfCT` | 契約審核用印申請單(Ver.6) | 46 |
| `PKG16030943796762` | tryauto | 43 |
| `dfRaise` | 薪資異動調整單 | 40 |
| `TIPTOPPROCESSPKG_afat108` | 資產報廢維護作業 | 36 |
| `dfitrequest` | 資訊系統需求單 | 36 |
| `PKG16213877031831` | 異常處理單 | 33 |
| `TIPTOPPROCESSPKG_apmt910` | 採購變更單維護作業 | 33 |
| `PKG16260529004741` | 客戶抱怨處理單 | 28 |
| `dfdocument` | 公文取號表單 | 27 |
| `APPFORMPROCESSPKG_ESSF51` | 加班計畫申請單(多時段) | 24 |
| `dfsuggest_tradelearn` | 出差心得報告簽呈﹝國貿﹞ | 24 |
| `dfntrequest` | 資訊裝置需求單 | 23 |
| `dfprint` | 檔案/用印申請單 | 23 |
| `dfInspection` | 廠內檢測需求單 | 21 |
| `dfexit` | 離職申請單 | 20 |
| `dfseal` | 用印申請單 | 19 |
| `dfMarketing` | 行銷總需求單 | 17 |
| `PKG15125301038001` | testAttachment | 15 |
| `dfbationperiod` | 新進人員試用期滿考核暨心得報告 | 15 |
| `PKG15519497947761` | 系統許可權申請單測試 | 14 |
| `TIPTOPPROCESSPKG_aapt110` | 廠商進貨發票請款作業 | 14 |
| `cyrequest` | 誠億需求單 | 14 |
| `TIPTOPPROCESSPKG_axmt410` | 請購單維護作業 | 13 |
| `dfchrequest` | 變更申請單 | 13 |
| `dfcnexception` | 管制異常處理需求單 | 12 |
| `dfouttraining` | 外派訓練申請表 | 12 |
| `3ActTemplate` | 三關流程樣板 | 11 |
| `dfsupplement` | 人員增補申請單 | 9 |
| `DG_IMG` | 範本_IMG測試流程 | 8 |
| `dfmagsug` | 董事長簽呈 | 7 |
| `TIPTOPPROCESSPKG_apmt420` | 請購單維護作業 | 6 |
| `dfCT_auth` | 系統許可權申請表測試 | 6 |
| `PKG15783649990861` | IMG測試 | 5 |
| `PKG16039638272041` | 工安/傷事件調查、處理紀錄單 | 5 |
| `PKG16073277816794` | trytest | 4 |
| `newdfotinspection` | 測試委外 | 4 |
| `PKG15325862095821` | 契約審核用印申請單 | 3 |
| `dfcreditapply` | 信用額度評估申請單 | 3 |
| `dftest` | 物品測試單 | 3 |
| `APPFORMPROCESSPKG_ESSF23` | 調職申請單 | 2 |
| `APPFORMPROCESSPKG_ESSF26` | 獎懲申請單 | 2 |
| `APPFORMPROCESSPKG_ESSF69` | 員工異動申請單 | 2 |
| `PKG16164678782641` | New Package | 2 |
| `PKG17477256337401` | AAATest | 2 |
| `TIPTOPPROCESSPKG_axrt300` | 應收帳款維護作業 | 2 |
| `ylsuggest` | 源利簽呈 | 2 |
| `PKG14943200618791` | TeatMail | 1 |
| `PKG16024924398521` | testdf | 1 |
| `PKG16030897529481` | try | 1 |
| `Subflow_10` | Subflow | 1 |
| `TIPTOPPROCESSPKG_afat105` | 固定資產改良作業 | 1 |
| `cgsuggest2` | 綠遠公司簽呈V2 | 1 |
| `dfcreditevl3` | 信用額度評估表 | 1 |
| `dfsuggest_tradechinapay2` | 源利出款簽呈【國貿】 | 1 |
| `APPFORMPROCESSPKG_ESSF05` | 加班計劃申請單 | 0 |
| `APPFORMPROCESSPKG_ESSF25` | ESS表單測試_25 | 0 |
| `APPFORMPROCESSPKG_ESSF27` | ESS表單測試_27 | 0 |
| `APPFORMPROCESSPKG_ESSF28` | ESS表單測試_28 | 0 |
| `APPFORMPROCESSPKG_ESSF72` | 員工異動申請 | 0 |
| `ESSF72` | 員工報到 | 0 |
| `PKG15505448127831` | 許可權申請 | 0 |
| `PKG16030943796762_new` | 資訊系統帳號申請單(new) | 0 |
| `PKG16062700543641_clone` | 委外檢測申請單(新版) | 0 |
| `PKG16315868167123` | Muti Form | 0 |
| `PRO14906802587992` | Subflow Process: 費用類 | 0 |
| `TIPTOPPROCESSPKG_aapt150` | 廠商預付請款作業 | 0 |
| `TIPTOPPROCESSPKG_afat102_clone` | 資產部門移轉作業 | 0 |
| `cgexpense` | 酷綠費用報銷單 | 0 |
| `dfActivity` | 活動企劃驗收單 | 0 |
| `dfBusinessCard` | 名片管理系統 | 0 |
| `dfassetschange` | 資產異動申請單 | 0 |
| `testcgsuggest` | 【測試】酷綠簽呈 | 0 |
| `testdfexpense` | 【測試】出差旅費報支單 | 0 |
| `testdfgovernment_clone` | 【測試】內部聯絡單 | 0 |
| `testdfgovernment_clone_clone` | 【測試】需求單 | 0 |
| `testdfpurchase` | 【測試】請購(修)申請單 | 0 |
| `testdfsale` | 【測試】銷貨申請單 | 0 |
| `testdfsale_b` | 【測試】業務處銷貨申請單 | 0 |
| `testdfsuggest` | 【測試】簽呈 | 0 |
| `testdftake` | 【測試】物品領用單 | 0 |
| `testdfwaorder` | 【測試】加盟物品訂購單 | 0 |
| `ylpurchase_clone` | 源利請購(修)申請單 | 0 |

**表單定義對照表（formId → 中文表單名，共 144 個）**

| formId（formSerialNumber 前綴） | 中文表單名 |
| --- | --- |
| `aapt110` | 廠商進貨發票請款作業 (aapt110) |
| `aapt120` | 雜項應付款項請款作業 (aapt120) |
| `aapt150` | 廠商預付請款作業 (aapt150) |
| `afat102` | 資產部門移轉作業 (afat102) |
| `afat102_clone` | 資產部門移轉作業 (afat102) |
| `afat105` | 固定資產改良作業 (afat105) |
| `afat108` | 資產報廢維護作業 (afat108) |
| `Amber` | Amber |
| `apmt420` | 請購單維護作業 (apmt420) |
| `apmt540` | 採購單維護作業 (apmt540) |
| `apmt910` | 採購變更單維護作業 (apmt910) |
| `authtest` | authtest |
| `axmt410` | 一般訂單維護作業 (axmt410) |
| `axrt300` | 應收帳款維護作業 (axrt300) |
| `BBBTest` | BBBTest |
| `cgexpense` | 酷綠費用報銷單 |
| `cgsuggest` | 酷綠公司簽呈 |
| `DF_IT_0001` | 帳戶申請表 |
| `dfActivity` | 活動企劃驗收單 |
| `dfassetschange` | 資產異動申請單 |
| `dfassetschangers` | dfassetschangers |
| `dfauth` | 資訊系統帳號申請 |
| `dfauth_new` | 資訊系統帳號申請 |
| `dfbasedata` | 簽呈 |
| `dfbationperiod` | 新進人員試用期滿考核暨心得報告 |
| `dfBusinessCard` | 名片管理系統 |
| `dfchecklist` | 離職人員交接單 |
| `dfchrequest` | 變更申請單 |
| `dfcnexception` | 管制異常處理需求單 |
| `dfcomplaint` | 客訴抱怨單 |
| `dfcreditapply` | 信用額度評估申請單 |
| `dfCreditEvaluate` | 新增客戶信用額度評估表 |
| `dfcreditevl` | 客戶信用額度評估表 |
| `dfCRMBankInfo` | CRM銀行資料新增/修改申請單 |
| `dfCT` | 契約審核用印申請單 |
| `dfCT_auth` | 系統許可權申請表測試 |
| `dfCTtest` | 契約審核用印申請單 |
| `dfDesign` | 設計需求驗收單 |
| `dfDocChange` | 檔案變更申請單 |
| `dfdocument` | 公文取號表單 |
| `dfeventsurvey` | dfeventsurvey |
| `dfexit` | dfexit |
| `dfexpense` | 出差旅費報支單 |
| `dffailproduct` | 不合格品處置單 |
| `dfgovernment` | 內部聯絡單 |
| `dfInspection` | 廠內檢測需求單 |
| `dfintern` | 實習生產攜生 |
| `dfITP001` | dfITP001 |
| `dfitrequest` | 資訊系統需求單 |
| `dfjobdescription` | 工作(職務)說明書 |
| `dfmagsug` | 董事長簽呈 |
| `dfMarket1` | 設計需求 |
| `dfMarket2` | 活動企劃 |
| `dfMarket3` | 素材授權申請表單 |
| `dfMarket4` | 對外曝光申請表單 |
| `dfMarket5` | 行銷許可權申請表單 |
| `dfMarket6` | 行銷物品線上清單 |
| `dfMarketing` | 行銷總需求單 |
| `dfNewResignation` | 離職申請單 |
| `dfntrequest` | 資訊裝置需求單 |
| `dfotinspection` | 委外檢測申請單 |
| `dfotinspection_clone` | 委外檢測申請單 |
| `dfouttraining` | 外派訓練申請表 |
| `dfprint` | 檔案/用印申請單 |
| `dfpurchase` | 請購(修)申請單 |
| `dfRaise` | dfRaise |
| `dfrequest` | 需求單 |
| `dfResignation` | 離職申請單 |
| `dfsale` | 銷貨申請單 |
| `dfsale_b` | 業務處銷貨申請單 |
| `dfseal` | 用印申請單 |
| `dfsuggest` | 簽呈 |
| `dfsuggest_clone` | 簽呈(1) |
| `dfsupplement` | 人員增補申請單 |
| `dftake` | 物品領用單 |
| `dftest` | 物品測試單 |
| `dftrialexperience` | 試用期滿心得表 |
| `dfunusual` | 異常處理單 |
| `dfwaorder` | 加盟物品訂購單 |
| `DG_TEST_IMG` | DG_TEST_IMG |
| `ESSF01` | ESSF01排班申請 |
| `ESSF03` | ESSF03補刷卡申請 |
| `ESSF04` | ESSF04加班申請 |
| `ESSF05` | ESSF05加班計劃申請 |
| `ESSF06` | 加班補休申請單 |
| `ESSF07` | ESSF07請假申請 |
| `ESSF08` | ESSF08積休申請 |
| `ESSF17` | 銷假申請單 |
| `ESSF20` | ESSF20出差申請 |
| `ESSF21` | ESSF21出差登記 |
| `ESSF22` | ESSF22調職調薪申請 |
| `ESSF23` | ESSF23調職申請 |
| `ESSF24` | ESSF24調薪申請 |
| `ESSF25` | ESSF25轉正申請 |
| `ESSF26` | ESSF26獎懲申請 |
| `ESSF27` | ESSF27離職申請 |
| `ESSF28` | ESSF28人力需求申請 |
| `ESSF29` | ESSF29轉正調薪申請 |
| `ESSF31` | ESSF31招聘計畫 |
| `ESSF32` | ESSF32應聘人員面試 |
| `ESSF33` | ESSF33應聘人員筆試 |
| `ESSF34` | ESSF34錄用申請 |
| `ESSF41` | ESSF41考核計劃 |
| `ESSF42` | ESSF42自定義考核指標 |
| `ESSF43` | ESSF43述職報告 |
| `ESSF44` | ESSF44考核評分 |
| `ESSF46` | ESSF46考核申訴 |
| `ESSF47` | ESSF47考核改進 |
| `ESSF50` | ESSF50班次變更申請 |
| `ESSF51` | ESSF51加班計畫申請(多時段) |
| `ESSF52` | ESSF52投班申請 |
| `ESSF52C1` | ESSF52C1班次互換 |
| `ESSF52C2` | ESSF52C2班次變更 |
| `ESSF53` | ESSF53排班確認 |
| `ESSF60` | ESSF60講師資格申請 |
| `ESSF61` | ESSF61課程開發申請 |
| `ESSF62` | ESSF62培訓預算申請 |
| `ESSF63` | ESSF63培訓需求採集 |
| `ESSF64` | ESSF64培訓計畫申請 |
| `ESSF66` | ESSF66培訓評估 |
| `ESSF67` | ESSF67培訓報名 |
| `ESSF68` | ESSF68取消培訓報名 |
| `ESSF69` | ESSF69員工異動申請 |
| `ESSF72` | ESSF72員工報到申請 |
| `ESSF74` | ESSF74資源申領 |
| `ESSF75` | ESSF75資源歸還 |
| `ESSF76` | ESSF76召募改進建議 |
| `ESSF77` | ESSF77入職推薦申請單 |
| `ESSF93` | ESSF93不加班原因申請 |
| `HR004_clone` | 系統許可權異動申請單 |
| `HrAbsenceFormsRWD` | EFGP請假單 |
| `MIS004` | 應用系統使用需求單 |
| `newdfeventsurvey` | 工安、工傷事故調查暨處理紀錄單(NEW) |
| `newdfotinspection` | newdfotinspection |
| `R_S_M3030_067` | 應用系統開發/維護申請單 |
| `R_S_M3030_067_A` | 應用系統開發/維護驗收單 |
| `TEST` | TEST |
| `test` | test |
| `testAttachment` | testAttachment |
| `testdfpurchase` | 請購(修)申請單 |
| `testdfsale_b` | 業務處銷貨申請單 |
| `TESTDropdown` | TESTDropdown |
| `trytest` | trytest |
| `ylsuggest` | 源利簽呈 |

**MLANGUAGE 三語 UI 標籤**：共 502 筆繁體（`zh_TW`）標籤，鍵為 `group_type`+`group_id`+`field_id`（對應應用層欄位，非 DB 欄位）。取樣：

| group_type | group_id | field_id | 繁體(zh_TW) | en_US |
| --- | --- | --- | --- | --- |
| MD | `ecp_public` | `add_failure` | 新增失敗 | Add failed |
| MD | `ecp_public` | `add_success` | 新增成功 | successfully added |
| MD | `ecp_public` | `confirm_batch_del` | 確認刪除選中資料嗎 | Are you sure you want to delete the selected data |
| MD | `ecp_public` | `confirm_del` | 確認刪除該條資料嗎 | Are you sure you want to delete this data |
| MD | `ecp_public` | `del_failure` | 刪除失敗 | failed to delete |
| MD | `ecp_public` | `del_success` | 刪除成功 | successfully deleted |
| MD | `ecp_public` | `del_success` | 刪除成功 | successfully deleted |
| MD | `ecp_public` | `edit_failure` | 修改失敗 | fail to edit |
| MD | `ecp_public` | `edit_success` | 修改成功 | successfully modified |
| MD | `ecp_public` | `info_failure` | 獲取失敗 | Getting information failure |
| MD | `ecp_public` | `input` | 請輸入 | Please input |
| MD | `ecp_public` | `is_length` | 長度不能超過32位 | Length cannot exceed 32 bits |
| MD | `ecp_public` | `is_not_null` | 不能為空 | Can not be empty |
| MD | `ecp_public` | `is_used` | 正在使用，不能刪除 | In use and cannot be deleted |
| MD | `ecp_public` | `not_recover` | 刪除後將無法恢復 | Cannot be restored after deletion |
| MD | `ecp_public` | `repeat` | 重復，請重新輸入 | repeat, please re-enter |
| MD | `ecp_public` | `select` | 請選擇 | Please choose |
| MD | `link_home` | `select_link` | 請選擇連結分類 | Please select a link type |
| MD | `module_form` | `page_info_failure` | 首頁資料獲取失敗 | Homepage data acquisition failed |
| MD | `module_form` | `remind_language` | 選中語系新增已完成，請重新選擇 | The selected language family has been added, please re select |

> ⚠️ 此對照賦予「**資料的業務含義**」（這筆是什麼流程／表單），但仍**無法**翻譯個別欄位名（如 `TB2`、`hdnJobId`）——欄位語意需另查各表單的 form-field 定義。


## 4. Table 清單（依估計列數排序）

| # | 表名 | 中文名/說明 | 欄位數 | 估計列數 | 隱含關聯數 |
| ---: | --- | --- | ---: | ---: | ---: |
| 1 | `ChangeActivityStateAudit` |  | 10 | 2,145,583 | 0 |
| 2 | `ChangeWorkItemStateAudit` |  | 10 | 1,427,104 | 0 |
| 3 | `WorkStep` |  | 10 | 717,258 | 0 |
| 4 | `WorkItem` |  | 26 | 716,995 | 0 |
| 5 | `ParticipantActivityInstance` |  | 27 | 713,005 | 0 |
| 6 | `ActivityDefinition` |  | 69 | 431,679 | 0 |
| 7 | `TransitionRestriction` |  | 5 | 431,679 | 0 |
| 8 | `NotificationContent` |  | 10 | 417,405 | 0 |
| 9 | `TransitionReference` |  | 4 | 417,002 | 0 |
| 10 | `TransitionDefinition` |  | 9 | 416,665 | 0 |
| 11 | `LocalRelevantData` |  | 6 | 385,201 | 0 |
| 12 | `ActivityNotification` |  | 8 | 370,754 | 0 |
| 13 | `ParticipantDefinition` |  | 25 | 340,322 | 0 |
| 14 | `ParticipantDefinition2` |  | 25 | 333,533 | 0 |
| 15 | `ChangeProcessStateAudit` |  | 8 | 301,626 | 0 |
| 16 | `StringWorkflowRuntimeValue` |  | 3 | 233,317 | 0 |
| 17 | `IAppDefContainer_AppDef` |  | 2 | 210,297 | 0 |
| 18 | `ProcessNotification` |  | 10 | 153,507 | 0 |
| 19 | `FormInstance` |  | 8 | 151,566 | 0 |
| 20 | `ProcessContext` |  | 5 | 151,537 | 0 |
| 21 | `ProcessInstance` |  | 36 | 151,497 | 0 |
| 22 | `LicenseStatRcd` |  | 3 | 148,716 | 0 |
| 23 | `RelevantDataDefinition` |  | 10 | 133,235 | 0 |
| 24 | `AppFormActivityRecord` |  | 10 | 116,542 | 0 |
| 25 | `dfsale_detail` |  | 11 | 110,487 | 0 |
| 26 | `BoundViewInformation` |  | 6 | 105,641 | 0 |
| 27 | `ActualParameter` |  | 4 | 96,030 | 0 |
| 28 | `Tool` |  | 10 | 95,031 | 0 |
| 29 | `BlockActivityInstance` |  | 14 | 90,771 | 0 |
| 30 | `WorkAssignment` |  | 11 | 86,991 | 0 |
| 31 | `LocalNoticeWorkItem` |  | 11 | 61,722 | 0 |
| 32 | `DBRsrcBundle` |  | 7 | 61,651 | 0 |
| 33 | `dfsale` |  | 44 | 55,038 | 0 |
| 34 | `Implementation` |  | 2 | 51,804 | 0 |
| 35 | `FormOperationDefinition` |  | 3 | 48,948 | 0 |
| 36 | `ProcessDefinition` |  | 33 | 48,092 | 0 |
| 37 | `ProcessPackage_ProcessDef` |  | 2 | 47,915 | 0 |
| 38 | `CustomProcessPackage` |  | 19 | 46,303 | 0 |
| 39 | `ActivitySetDefinition` |  | 4 | 45,768 | 0 |
| 40 | `FormFieldAccessDefinition` |  | 7 | 45,500 | 0 |
| 41 | `OJB_DSET_ENTRIES` |  | 4 | 34,049 | 0 |
| 42 | `OJB_DSET` |  | 2 | 31,378 | 0 |
| 43 | `dfpurchase_detail` |  | 8 | 31,207 | 0 |
| 44 | `NoCmDocument` |  | 14 | 17,917 | 0 |
| 45 | `DocServer_IDocument` |  | 2 | 17,902 | 0 |
| 46 | `dfpurchase` |  | 36 | 15,967 | 0 |
| 47 | `WorkAssignment_Label` |  | 2 | 15,433 | 0 |
| 48 | `DecisionLevel` |  | 6 | 12,897 | 0 |
| 49 | `DecisionRule` |  | 4 | 11,303 | 0 |
| 50 | `ConditionDefinition` |  | 4 | 8,192 | 0 |
| 51 | `dfsale_b_detail` |  | 10 | 8,006 | 0 |
| 52 | `dfinventory_detail` |  | 11 | 7,334 | 0 |
| 53 | `BasicType` |  | 3 | 7,076 | 0 |
| 54 | `dfsuggest` |  | 17 | 6,077 | 0 |
| 55 | `FunctionDefinition` |  | 6 | 5,780 | 0 |
| 56 | `dfsale_b` |  | 41 | 5,508 | 0 |
| 57 | `BamActInstData` |  | 17 | 5,116 | 0 |
| 58 | `DecisionCondition` |  | 6 | 5,041 | 0 |
| 59 | `FormalParameter` |  | 9 | 4,434 | 0 |
| 60 | `BamWorkItemData` |  | 24 | 3,635 | 0 |
| 61 | `UserLogInOutRecord` |  | 13 | 3,518 | 0 |
| 62 | `RedefinableHeader` |  | 7 | 3,343 | 0 |
| 63 | `dftake_detail` |  | 11 | 3,183 | 0 |
| 64 | `SYN_Functions` |  | 8 | 3,108 | 0 |
| 65 | `SYN_Employee` |  | 4 | 3,064 | 0 |
| 66 | `SessionBeanApplication` |  | 19 | 3,053 | 0 |
| 67 | `SYN_Users` |  | 10 | 3,026 | 0 |
| 68 | `StrategyAssignDefinition` |  | 4 | 2,898 | 0 |
| 69 | `OJB_DLIST_ENTRIES` |  | 4 | 2,827 | 0 |
| 70 | `OJB_DLIST` |  | 2 | 2,687 | 0 |
| 71 | `Functions` |  | 8 | 2,589 | 0 |
| 72 | `Employee` |  | 6 | 2,539 | 0 |
| 73 | `Users` |  | 26 | 2,514 | 0 |
| 74 | `Route` |  | 2 | 2,431 | 0 |
| 75 | `SYN_SubstituteDefinition` |  | 4 | 2,177 | 0 |
| 76 | `BlockActivity` |  | 3 | 2,034 | 0 |
| 77 | `ReassignWorkItemAuditData` |  | 19 | 2,013 | 0 |
| 78 | `DecisionRuleList` |  | 9 | 1,974 | 0 |
| 79 | `FormDefinition` |  | 19 | 1,906 | 0 |
| 80 | `FormType` |  | 3 | 1,896 | 0 |
| 81 | `TimeEstimation` |  | 5 | 1,847 | 0 |
| 82 | `BpmGateWay` |  | 2 | 1,814 | 0 |
| 83 | `ProcessDefinitionHeader` |  | 11 | 1,618 | 0 |
| 84 | `ProcessViewInformation` |  | 4 | 1,618 | 0 |
| 85 | `ProcessPackageHeader` |  | 10 | 1,608 | 0 |
| 86 | `ProcessPackage` |  | 19 | 1,597 | 0 |
| 87 | `dfgovernment` |  | 18 | 1,505 | 0 |
| 88 | `BpmEvent` |  | 4 | 1,406 | 0 |
| 89 | `dftake` |  | 23 | 1,356 | 0 |
| 90 | `BamProInstData` |  | 22 | 1,230 | 0 |
| 91 | `ConformanceClass` |  | 3 | 1,133 | 0 |
| 92 | `cgsuggest` |  | 25 | 994 | 0 |
| 93 | `dfexpense_detail` |  | 23 | 904 | 0 |
| 94 | `PackageInvokeAuthority` |  | 6 | 903 | 0 |
| 95 | `LocalToDoWorkItem` |  | 10 | 899 | 0 |
| 96 | `ProcessDefinitionSys` |  | 5 | 639 | 0 |
| 97 | `Draft` |  | 7 | 594 | 0 |
| 98 | `ProcessMappingKey` |  | 13 | 593 | 0 |
| 99 | `DraftHeader` |  | 10 | 575 | 0 |
| 100 | `MLANGUAGE` |  | 14 | 502 | 0 |
| 101 | `Nos` |  | 4 | 442 | 0 |
| 102 | `dfwaorder_detail` |  | 9 | 416 | 0 |
| 103 | `MobileOAuthWeChatUser` |  | 10 | 395 | 0 |
| 104 | `SYN_Unit` |  | 7 | 392 | 0 |
| 105 | `ResponsibleDefinition` |  | 5 | 362 | 0 |
| 106 | `SYN_UnitRelation` |  | 4 | 330 | 0 |
| 107 | `dfexpense` |  | 40 | 327 | 0 |
| 108 | `OrganizationUnit` |  | 10 | 325 | 0 |
| 109 | `FormRepository` |  | 14 | 255 | 0 |
| 110 | `dfbasedata` |  | 17 | 254 | 0 |
| 111 | `InstanceSerialNumber` |  | 6 | 250 | 0 |
| 112 | `SystemVariable` |  | 11 | 240 | 0 |
| 113 | `dfwaorder` |  | 25 | 218 | 0 |
| 114 | `Mails` |  | 6 | 217 | 0 |
| 115 | `ProgramAccessRight` |  | 9 | 211 | 0 |
| 116 | `dftest_detail` |  | 11 | 211 | 0 |
| 117 | `AppFormAttachment` |  | 4 | 205 | 0 |
| 118 | `ProgramDefinition` |  | 10 | 199 | 0 |
| 119 | `FunctionLevel` |  | 6 | 178 | 0 |
| 120 | `afat102_s_fat` |  | 19 | 164 | 0 |
| 121 | `aapt120_s_apb` |  | 14 | 157 | 0 |
| 122 | `FormDefinitionCmItem` |  | 8 | 153 | 0 |
| 123 | `dfstuffmatch` |  | 45 | 125 | 0 |
| 124 | `SYN_UnitManager` |  | 4 | 118 | 0 |
| 125 | `dfCRMBankInfo` |  | 43 | 118 | 0 |
| 126 | `dfinventory` |  | 17 | 111 | 0 |
| 127 | `dfrequest` |  | 17 | 107 | 0 |
| 128 | `afat102` |  | 21 | 106 | 0 |
| 129 | `OrganizationUnitLevel` |  | 6 | 105 | 0 |
| 130 | `ProcessPackageCmItem` |  | 8 | 103 | 0 |
| 131 | `aapt120` |  | 58 | 100 | 0 |
| 132 | `Group_User` |  | 2 | 85 | 0 |
| 133 | `AttachmentAuthority` |  | 6 | 71 | 0 |
| 134 | `Phrase` |  | 6 | 71 | 0 |
| 135 | `FormScriptTemplate` |  | 10 | 69 | 0 |
| 136 | `dffailproduct_detail` |  | 12 | 64 | 0 |
| 137 | `Organization` |  | 4 | 59 | 0 |
| 138 | `Groups` |  | 6 | 55 | 0 |
| 139 | `McloudMappingKey` |  | 3 | 55 | 0 |
| 140 | `BamWorkAssignmentData` |  | 23 | 47 | 0 |
| 141 | `AuthorityRight` |  | 8 | 42 | 0 |
| 142 | `dfCreditEvaluate` |  | 55 | 40 | 0 |
| 143 | `FormSqlClause` |  | 9 | 29 | 0 |
| 144 | `ModuleDefinition` |  | 10 | 27 | 0 |
| 145 | `WebApplication` |  | 15 | 27 | 0 |
| 146 | `dfCT` |  | 36 | 27 | 0 |
| 147 | `dffailproduct` |  | 39 | 27 | 0 |
| 148 | `FormInstance_BAK1212` |  | 8 | 26 | 0 |
| 149 | `FormTypeCategory` |  | 9 | 25 | 0 |
| 150 | `dfseal_detail` |  | 8 | 24 | 0 |
| 151 | `ChatFileProperties` |  | 9 | 22 | 0 |
| 152 | `AuthorityGroup` |  | 7 | 21 | 0 |
| 153 | `AuthorityScopeSlot` |  | 7 | 21 | 0 |
| 154 | `AuthorityUnits` |  | 8 | 21 | 0 |
| 155 | `SqlAllowedForm` |  | 4 | 21 | 0 |
| 156 | `afat108` |  | 16 | 21 | 0 |
| 157 | `afat108_s_fbh` |  | 13 | 21 | 0 |
| 158 | `dftest` |  | 23 | 20 | 0 |
| 159 | `AttachmentDefinition` |  | 6 | 17 | 0 |
| 160 | `PerDataPro` |  | 13 | 16 | 0 |
| 161 | `SYN_Org` |  | 3 | 16 | 0 |
| 162 | `dfcontact` |  | 11 | 16 | 0 |
| 163 | `ArchiveProperties` |  | 4 | 15 | 0 |
| 164 | `dfdocument` |  | 20 | 15 | 0 |
| 165 | `dfseal` |  | 32 | 15 | 0 |
| 166 | `FavoriteProcess` |  | 5 | 13 | 0 |
| 167 | `FormCategory` |  | 3 | 13 | 0 |
| 168 | `ProcessPackageCategory` |  | 5 | 13 | 0 |
| 169 | `AttachmentType` |  | 3 | 12 | 0 |
| 170 | `TrmProperties` |  | 8 | 10 | 0 |
| 171 | `JMS_ROLES` |  | 2 | 9 | 1 |
| 172 | `dfstuff` |  | 19 | 9 | 0 |
| 173 | `dfsuggest_clone` |  | 17 | 9 | 0 |
| 174 | `ecp_module_page` |  | 9 | 9 | 0 |
| 175 | `ecp_page_module` |  | 22 | 9 | 0 |
| 176 | `dfusual` |  | 11 | 8 | 0 |
| 177 | `testdfsuggest` |  | 17 | 8 | 0 |
| 178 | `ArchiveEventRecord` |  | 10 | 7 | 0 |
| 179 | `ArchiveProcessDetail` |  | 10 | 7 | 0 |
| 180 | `DataAccessDefinition` |  | 14 | 7 | 0 |
| 181 | `IndustryCategory` |  | 9 | 7 | 0 |
| 182 | `PerDataProType` |  | 5 | 7 | 0 |
| 183 | `WorkflowServer` |  | 9 | 7 | 0 |
| 184 | `dfcomplaint_39` |  | 35 | 7 | 0 |
| 185 | `CriticalProcessHintFields` |  | 9 | 6 | 0 |
| 186 | `FormScriptCategory` |  | 7 | 6 | 0 |
| 187 | `ISOProperties` |  | 6 | 6 | 0 |
| 188 | `OrgWizardAuthorityScope` |  | 7 | 6 | 0 |
| 189 | `testdfexpense_detail` |  | 23 | 6 | 0 |
| 190 | `CriticalMessageLog` |  | 12 | 5 | 1 |
| 191 | `DocType` |  | 5 | 5 | 0 |
| 192 | `IntegratedSessionBeanPara` |  | 15 | 5 | 0 |
| 193 | `JMS_USERS` |  | 3 | 5 | 0 |
| 194 | `ProcessUserFocus` |  | 5 | 5 | 0 |
| 195 | `SubFlow` |  | 6 | 5 | 0 |
| 196 | `dfDocChange` |  | 34 | 5 | 0 |
| 197 | `AnalyzedServiceParameter` |  | 11 | 4 | 0 |
| 198 | `FavoriteMenu` |  | 7 | 4 | 0 |
| 199 | `LicenseReg` |  | 3 | 4 | 0 |
| 200 | `MTSProperties` |  | 6 | 4 | 0 |
| 201 | `SysLanguage` |  | 7 | 4 | 0 |
| 202 | `UpgradeRecord` |  | 4 | 4 | 0 |
| 203 | `dfcnexception` |  | 22 | 4 | 0 |
| 204 | `dfcomplaint_43` |  | 35 | 4 | 0 |
| 205 | `dfitrequest` |  | 23 | 4 | 0 |
| 206 | `dfntrequest` |  | 21 | 4 | 0 |
| 207 | `ApiParameters` |  | 2 | 3 | 0 |
| 208 | `MLANGUAGE_RELATION` |  | 7 | 3 | 0 |
| 209 | `MTSParamFormat` |  | 12 | 3 | 0 |
| 210 | `OauthSetting` |  | 13 | 3 | 0 |
| 211 | `PrsInsLvl` |  | 6 | 3 | 0 |
| 212 | `SqlAllowedJsp` |  | 4 | 3 | 0 |
| 213 | `UserName` |  | 5 | 3 | 0 |
| 214 | `WebServicesApplication` |  | 11 | 3 | 0 |
| 215 | `WizardAuthority` |  | 6 | 3 | 0 |
| 216 | `dfcustapp` |  | 30 | 3 | 0 |
| 217 | `dfmagsug` |  | 20 | 3 | 0 |
| 218 | `dfotinspection` |  | 35 | 3 | 0 |
| 219 | `testdfexpense` |  | 40 | 3 | 0 |
| 220 | `testdfgovernment` |  | 16 | 3 | 0 |
| 221 | `AnalyzedService` |  | 11 | 2 | 0 |
| 222 | `AuthorityScope` |  | 7 | 2 | 0 |
| 223 | `CombinationService` |  | 6 | 2 | 0 |
| 224 | `CriticalConditionDefinition` |  | 4 | 2 | 0 |
| 225 | `CriticalDefinition` |  | 7 | 2 | 0 |
| 226 | `CriticalFocusProcess` |  | 8 | 2 | 0 |
| 227 | `CriticalPriority` |  | 7 | 2 | 0 |
| 228 | `CriticalProcessDefinition` |  | 11 | 2 | 2 |
| 229 | `CuzModuleDefinition` |  | 7 | 2 | 0 |
| 230 | `ExternalService` |  | 7 | 2 | 0 |
| 231 | `FormCategoryAccessRight` |  | 7 | 2 | 0 |
| 232 | `GuardServiceExceptionRecord` |  | 6 | 2 | 0 |
| 233 | `IntegratedSessionBeanApp` |  | 13 | 2 | 0 |
| 234 | `MobileScheduleRecord` |  | 9 | 2 | 0 |
| 235 | `OrganizationUnitProperty` |  | 5 | 2 | 0 |
| 236 | `PackageCategoryAccessRight` |  | 7 | 2 | 0 |
| 237 | `custAttachedFilesToForm` |  | 6 | 2 | 0 |
| 238 | `dfCT_auth` |  | 99 | 2 | 0 |
| 239 | `dfcomplaint_42` |  | 36 | 2 | 0 |
| 240 | `dfcreditapply` |  | 23 | 2 | 0 |
| 241 | `dfstuffmatch_attach` |  | 5 | 2 | 0 |
| 242 | `testdfpurchase_detail` |  | 8 | 2 | 0 |
| 243 | `AllUserUnit` |  | 4 | 1 | 0 |
| 244 | `AutoAgent` |  | 4 | 1 | 0 |
| 245 | `CmDocument` |  | 10 | 1 | 0 |
| 246 | `CrmModel` |  | 12 | 1 | 0 |
| 247 | `CuzPatternDefinition` |  | 7 | 1 | 0 |
| 248 | `DocCategoryType` |  | 7 | 1 | 0 |
| 249 | `DocCmItem` |  | 8 | 1 | 0 |
| 250 | `DocServer` |  | 9 | 1 | 0 |
| 251 | `ESSF26` |  | 55 | 1 | 0 |
| 252 | `GuardServiceReg` |  | 5 | 1 | 0 |
| 253 | `GuardServiseServer` |  | 5 | 1 | 0 |
| 254 | `HILOSEQUENCES` |  | 2 | 1 | 0 |
| 255 | `ISOCloudProperties` |  | 9 | 1 | 0 |
| 256 | `IntelligentLearningSchedule` |  | 4 | 1 | 0 |
| 257 | `Labels` |  | 7 | 1 | 0 |
| 258 | `MTSResourceType` |  | 8 | 1 | 0 |
| 259 | `MobileOAuthConfig` |  | 17 | 1 | 0 |
| 260 | `ObjectIdentity` |  | 5 | 1 | 0 |
| 261 | `PatternDefinition` |  | 6 | 1 | 0 |
| 262 | `PersonalizeExcludeUsers` |  | 1 | 1 | 0 |
| 263 | `SmartEmployees` |  | 10 | 1 | 0 |
| 264 | `SnGenRule` |  | 8 | 1 | 0 |
| 265 | `SubFlowActivityInstance` |  | 12 | 1 | 0 |
| 266 | `SysT100Config` |  | 6 | 1 | 0 |
| 267 | `SystemConfig` |  | 12 | 1 | 0 |
| 268 | `TFASetting` |  | 13 | 1 | 0 |
| 269 | `TiptopModel` |  | 12 | 1 | 0 |
| 270 | `TrmSourceForm` |  | 9 | 1 | 0 |
| 271 | `axmt410` |  | 78 | 1 | 0 |
| 272 | `axmt410_s_oeb` |  | 17 | 1 | 0 |
| 273 | `custRestfulAuthInfo` |  | 7 | 1 | 0 |
| 274 | `dfActivity` |  | 11 | 1 | 0 |
| 275 | `dfMarketing` |  | 93 | 1 | 0 |
| 276 | `dfResignation_10` |  | 21 | 1 | 0 |
| 277 | `dfchecklist_7` |  | 11 | 1 | 0 |
| 278 | `dfchrequest` |  | 30 | 1 | 0 |
| 279 | `dfcomplaint` |  | 35 | 1 | 0 |
| 280 | `dfprint` |  | 31 | 1 | 0 |
| 281 | `dfunusual_16` |  | 17 | 1 | 0 |
| 282 | `dfunusual_20` |  | 17 | 1 | 0 |
| 283 | `ecp_page_basic` |  | 25 | 1 | 0 |
| 284 | `ecp_page_range` |  | 11 | 1 | 0 |
| 285 | `testdfpurchase` |  | 36 | 1 | 0 |
| 286 | `testdfrequest` |  | 17 | 1 | 0 |
| 287 | `AbsenceRecord` |  | 7 | 0 | 0 |
| 288 | `AccessRightEntity` |  | 9 | 0 | 0 |
| 289 | `ActivityDefinitionEntity` |  | 70 | 0 | 0 |
| 290 | `AdapterApp` |  | 5 | 0 | 0 |
| 291 | `AdapterConfig` |  | 13 | 0 | 0 |
| 292 | `AdapterDingtalkTodoTask` |  | 17 | 0 | 0 |
| 293 | `AdapterUser` |  | 9 | 0 | 0 |
| 294 | `AnnouncementAttachment` |  | 10 | 0 | 0 |
| 295 | `AnnouncementData` |  | 13 | 0 | 0 |
| 296 | `AnnouncementEmergency` |  | 3 | 0 | 0 |
| 297 | `AnnouncementRecords` |  | 7 | 0 | 0 |
| 298 | `AnnouncementType` |  | 3 | 0 | 0 |
| 299 | `ArchiveExcludedProcess` |  | 6 | 0 | 0 |
| 300 | `ArchiveProcessInReduction` |  | 5 | 0 | 0 |
| 301 | `ArchiveProcessRule` |  | 10 | 0 | 0 |
| 302 | `ArchiveTimeSchedule` |  | 9 | 0 | 0 |
| 303 | `AssignmentNoPerPerson` |  | 5 | 0 | 0 |
| 304 | `AttachmentInstance` |  | 4 | 0 | 0 |
| 305 | `BamProcessRecord` |  | 26 | 0 | 0 |
| 306 | `BamSetting` |  | 6 | 0 | 0 |
| 307 | `BpmActivityMappingDocProp` |  | 12 | 0 | 0 |
| 308 | `BpmLane` |  | 6 | 0 | 0 |
| 309 | `BpmPool` |  | 5 | 0 | 0 |
| 310 | `ByReferenceParameter` |  | 5 | 0 | 0 |
| 311 | `ByValueParameter` |  | 6 | 0 | 0 |
| 312 | `ChatFileAssistedReading` |  | 7 | 0 | 0 |
| 313 | `ChatFileExecutionRecord` |  | 11 | 0 | 0 |
| 314 | `ChatFileExperience` |  | 12 | 0 | 0 |
| 315 | `ChatFileExperienceRecords` |  | 24 | 0 | 0 |
| 316 | `ChatFileExperienceSchedule` |  | 14 | 0 | 0 |
| 317 | `ChatFileISOTransferRecords` |  | 23 | 0 | 1 |
| 318 | `ChatFileKnowledge` |  | 11 | 0 | 1 |
| 319 | `ChatFileKnowledgeCategory` |  | 7 | 0 | 0 |
| 320 | `ChatFilePresetProblem` |  | 10 | 0 | 0 |
| 321 | `ChatFileQARecord` |  | 14 | 0 | 0 |
| 322 | `ChatFileTransferRecords` |  | 23 | 0 | 0 |
| 323 | `ChatFileUserManagement` |  | 8 | 0 | 0 |
| 324 | `ChatFileUserToken` |  | 10 | 0 | 0 |
| 325 | `CmItemAcsRight` |  | 6 | 0 | 0 |
| 326 | `CmItemCategory` |  | 5 | 0 | 0 |
| 327 | `CompositeType` |  | 6 | 0 | 0 |
| 328 | `ConnectedUserInfo` |  | 16 | 0 | 0 |
| 329 | `CustomAccessRight` |  | 5 | 0 | 0 |
| 330 | `CustomDataChooserConf` |  | 19 | 0 | 0 |
| 331 | `CustomQuery` |  | 17 | 0 | 0 |
| 332 | `CuzProgramDefinition` |  | 10 | 0 | 0 |
| 333 | `CuzProgramRefProcess` |  | 6 | 0 | 0 |
| 334 | `Deadline` |  | 6 | 0 | 0 |
| 335 | `DecisionConditionSharing` |  | 5 | 0 | 0 |
| 336 | `DecisionLevelSharing` |  | 6 | 0 | 0 |
| 337 | `DecisionPatterns` |  | 6 | 0 | 0 |
| 338 | `DecisionPatternsMapping` |  | 6 | 0 | 0 |
| 339 | `DecisionRuleListSharing` |  | 7 | 0 | 0 |
| 340 | `DecisionRuleSharing` |  | 4 | 0 | 0 |
| 341 | `DeclaredType` |  | 3 | 0 | 0 |
| 342 | `DefAccessRight` |  | 7 | 0 | 0 |
| 343 | `DefCmItem` |  | 10 | 0 | 0 |
| 344 | `DefEntity` |  | 14 | 0 | 0 |
| 345 | `DefaultSubstituteDefinition` |  | 8 | 0 | 0 |
| 346 | `DeliveryProcessConfiguration` |  | 26 | 0 | 0 |
| 347 | `DeliveryProcessInstance` |  | 26 | 0 | 0 |
| 348 | `DeployDocServer` |  | 8 | 0 | 0 |
| 349 | `DeployedUnit` |  | 6 | 0 | 0 |
| 350 | `DesignTempFile` |  | 8 | 0 | 0 |
| 351 | `DocAcsRightRecord` |  | 10 | 0 | 0 |
| 352 | `DocCategory` |  | 8 | 0 | 0 |
| 353 | `DocCmItem_AccessRight` |  | 2 | 0 | 0 |
| 354 | `DocCmItem_Category` |  | 2 | 0 | 0 |
| 355 | `DocCmItem_ISODocLevel` |  | 2 | 0 | 0 |
| 356 | `DocCmItem_ISODocType` |  | 2 | 0 | 0 |
| 357 | `DocCmItem_ISOFilePolicy` |  | 2 | 0 | 0 |
| 358 | `DocCmItem_RefDoc` |  | 2 | 0 | 0 |
| 359 | `DocDraft` |  | 7 | 0 | 1 |
| 360 | `DocMetadataDef` |  | 5 | 0 | 0 |
| 361 | `DocMetadataInst` |  | 5 | 0 | 0 |
| 362 | `DocNoReserved` |  | 16 | 0 | 1 |
| 363 | `Doc_Clause` |  | 2 | 0 | 0 |
| 364 | `Doc_DeployedUnit` |  | 2 | 0 | 0 |
| 365 | `Doc_Level` |  | 2 | 0 | 0 |
| 366 | `Doc_RelatedUnit` |  | 2 | 0 | 0 |
| 367 | `Documents` |  | 25 | 0 | 1 |
| 368 | `EBGForm` |  | 43 | 0 | 0 |
| 369 | `EBGForm_templateGrid` |  | 13 | 0 | 0 |
| 370 | `EBGHistoricalSigner` |  | 9 | 0 | 0 |
| 371 | `EBGPropertise` |  | 10 | 0 | 0 |
| 372 | `EBGSignerTemplate` |  | 8 | 0 | 0 |
| 373 | `EBGSignerTemplate_Users` |  | 6 | 0 | 0 |
| 374 | `EFGPIntePLMInfo` |  | 7 | 0 | 0 |
| 375 | `EPM_BudgetCreateForm` |  | 19 | 0 | 0 |
| 376 | `EPM_BudgetCreateForm_grid` |  | 27 | 0 | 0 |
| 377 | `EPM_BudgetDivertForm` |  | 34 | 0 | 0 |
| 378 | `EPM_BudgetReviseForm` |  | 22 | 0 | 0 |
| 379 | `EPM_BudgetReviseForm_grid` |  | 8 | 0 | 0 |
| 380 | `EPM_Category` |  | 11 | 0 | 0 |
| 381 | `EPM_CategoryLevel` |  | 4 | 0 | 0 |
| 382 | `EPM_CategoryLocal` |  | 4 | 0 | 0 |
| 383 | `EPM_Company` |  | 13 | 0 | 0 |
| 384 | `EPM_CompanyBudget` |  | 6 | 0 | 0 |
| 385 | `EPM_Config` |  | 9 | 0 | 0 |
| 386 | `EPM_CostCenter` |  | 18 | 0 | 0 |
| 387 | `EPM_CostCenterCategory` |  | 24 | 0 | 0 |
| 388 | `EPM_CostCenterDept` |  | 5 | 0 | 0 |
| 389 | `EPM_Currency` |  | 7 | 0 | 0 |
| 390 | `EPM_ExchangeRate` |  | 5 | 0 | 0 |
| 391 | `EPM_ExpenseForm` |  | 35 | 0 | 0 |
| 392 | `EPM_ExpenseForm_CM` |  | 37 | 0 | 0 |
| 393 | `EPM_ExpenseForm_CM_grid` |  | 45 | 0 | 0 |
| 394 | `EPM_ExpenseForm_grid` |  | 43 | 0 | 0 |
| 395 | `EPM_ExpenseForm_grid2` |  | 15 | 0 | 0 |
| 396 | `EPM_ExpenseForm_grid3` |  | 8 | 0 | 0 |
| 397 | `EPM_Local` |  | 3 | 0 | 0 |
| 398 | `EPM_PrepaidExpenseForm` |  | 37 | 0 | 0 |
| 399 | `EPM_PrepaidExpenseForm_grid` |  | 19 | 0 | 0 |
| 400 | `EPM_PrepaidVendorForm` |  | 51 | 0 | 0 |
| 401 | `EPM_PrepaidVendorForm_CM` |  | 51 | 0 | 0 |
| 402 | `EPM_PrepaidVendorForm_CM_grid` |  | 22 | 0 | 0 |
| 403 | `EPM_PrepaidVendorForm_grid` |  | 29 | 0 | 0 |
| 404 | `EPM_VendorRequestForm` |  | 53 | 0 | 0 |
| 405 | `EPM_VendorRequestForm_CM` |  | 55 | 0 | 0 |
| 406 | `EPM_VendorRequestForm_CM_grid` |  | 26 | 0 | 0 |
| 407 | `EPM_VendorRequestForm_grid` |  | 30 | 0 | 0 |
| 408 | `EPM_VendorRequestForm_grid2` |  | 15 | 0 | 0 |
| 409 | `ETL_ForDelete` |  | 1 | 0 | 0 |
| 410 | `ErrorCombineServiceRecord` |  | 4 | 0 | 0 |
| 411 | `ExceptionNotificationDef` |  | 6 | 0 | 0 |
| 412 | `ExceptionRetryDef` |  | 6 | 0 | 0 |
| 413 | `ExternalPackage` |  | 4 | 0 | 0 |
| 414 | `ExternalReference` |  | 5 | 0 | 0 |
| 415 | `FormColumnMask` |  | 6 | 0 | 0 |
| 416 | `FormDataObject` |  | 7 | 0 | 0 |
| 417 | `FormDesignAssistant` |  | 24 | 0 | 0 |
| 418 | `FormFieldAccessDefault` |  | 2 | 0 | 0 |
| 419 | `GlobalRelevantData` |  | 5 | 0 | 0 |
| 420 | `ISOAuthorityGroup` |  | 10 | 0 | 0 |
| 421 | `ISOAuthorityUsers` |  | 4 | 0 | 0 |
| 422 | `ISOClause` |  | 6 | 0 | 0 |
| 423 | `ISOCloudApplyDocsChangeRecord` |  | 11 | 0 | 0 |
| 424 | `ISOCloudApplyDocsRecord` |  | 15 | 0 | 0 |
| 425 | `ISODocCmItem` |  | 22 | 0 | 0 |
| 426 | `ISODocLevel` |  | 7 | 0 | 0 |
| 427 | `ISODocType` |  | 5 | 0 | 0 |
| 428 | `ISOFile` |  | 13 | 0 | 0 |
| 429 | `ISOFilePolicy` |  | 12 | 0 | 0 |
| 430 | `ISOFilePolicyMAC` |  | 4 | 0 | 0 |
| 431 | `ISOFilePolicyUnit` |  | 5 | 0 | 0 |
| 432 | `ISOFileReadingRecord` |  | 17 | 0 | 1 |
| 433 | `ISOFullTextSearch` |  | 5 | 0 | 1 |
| 434 | `ISOPaperRecord` |  | 14 | 0 | 1 |
| 435 | `ISOPortabilityCloudApplyRecord` |  | 27 | 0 | 0 |
| 436 | `ISOPortabilityCloudRecord` |  | 17 | 0 | 1 |
| 437 | `ISOPortabilityCloudUsers` |  | 8 | 0 | 0 |
| 438 | `ISOPortabilityCompany` |  | 14 | 0 | 0 |
| 439 | `ISOPortabilityMailDesign` |  | 9 | 0 | 0 |
| 440 | `ISOPortabilityRecord` |  | 16 | 0 | 0 |
| 441 | `ISOTracingData` |  | 5 | 0 | 0 |
| 442 | `ISOVettingRecord` |  | 24 | 0 | 1 |
| 443 | `ISOVettingRule` |  | 17 | 0 | 0 |
| 444 | `ISOWatermarkImagePattern` |  | 7 | 0 | 0 |
| 445 | `ISOWatermarkPattern` |  | 12 | 0 | 0 |
| 446 | `IndicatorDefinition` |  | 25 | 0 | 0 |
| 447 | `IntelligentLearningRecord` |  | 7 | 0 | 0 |
| 448 | `JMS_MESSAGES` |  | 5 | 0 | 1 |
| 449 | `JMS_SUBSCRIPTIONS` |  | 4 | 0 | 0 |
| 450 | `JMS_TRANSACTIONS` |  | 1 | 0 | 0 |
| 451 | `LayoutCmItem` |  | 10 | 0 | 0 |
| 452 | `LayoutEntity` |  | 13 | 0 | 0 |
| 453 | `LayoutEntity_Platform` |  | 2 | 0 | 0 |
| 454 | `MTSMeetingApply` |  | 20 | 0 | 0 |
| 455 | `MTSMeetingApply_Tasks` |  | 13 | 0 | 0 |
| 456 | `MTSMeetingApply_Users` |  | 7 | 0 | 0 |
| 457 | `MTSMeetingType` |  | 9 | 0 | 0 |
| 458 | `MTSResourceApply` |  | 7 | 0 | 0 |
| 459 | `MTSResourceManagement` |  | 16 | 0 | 0 |
| 460 | `MTSRoomApply` |  | 11 | 0 | 0 |
| 461 | `MTSTemplate` |  | 17 | 0 | 0 |
| 462 | `MTSTemplate_Users` |  | 4 | 0 | 0 |
| 463 | `MailApplication` |  | 13 | 0 | 0 |
| 464 | `MailTask` |  | 7 | 0 | 0 |
| 465 | `MobileCallBackConfig` |  | 5 | 0 | 0 |
| 466 | `MobileDynamicFormRecord` |  | 6 | 0 | 0 |
| 467 | `MobileGraphTemplates` |  | 4 | 0 | 0 |
| 468 | `MobileMessageSubscription` |  | 5 | 0 | 0 |
| 469 | `MobileOAuthWeChatOrganization` |  | 8 | 0 | 0 |
| 470 | `MobileSyncOrgConfig` |  | 5 | 0 | 0 |
| 471 | `MultiAPIconSwitch` |  | 3 | 0 | 0 |
| 472 | `MultiProcessRefRecord` |  | 13 | 0 | 0 |
| 473 | `NoCmDocumentAuth` |  | 7 | 0 | 0 |
| 474 | `OJB_DMAP` |  | 2 | 0 | 0 |
| 475 | `OJB_DMAP_ENTRIES` |  | 4 | 0 | 0 |
| 476 | `OJB_HL_SEQ` |  | 5 | 0 | 0 |
| 477 | `OJB_LOCKENTRY` |  | 5 | 0 | 0 |
| 478 | `OJB_NEXTVAL_SEQ` |  | 2 | 0 | 0 |
| 479 | `OJB_NRM` |  | 2 | 0 | 0 |
| 480 | `OauthAuthentication` |  | 7 | 0 | 0 |
| 481 | `OnlineReadWatermarkPattern` |  | 7 | 0 | 0 |
| 482 | `OrgUnit_OrgUnitProperty` |  | 2 | 0 | 0 |
| 483 | `ParticularRecord` |  | 6 | 0 | 0 |
| 484 | `ParticularRule` |  | 9 | 0 | 0 |
| 485 | `PercentagePerPerson` |  | 6 | 0 | 0 |
| 486 | `PerformanceData` |  | 10 | 0 | 0 |
| 487 | `PerformanceRecord` |  | 9 | 0 | 0 |
| 488 | `ProcessCtx_GblRelevantData` |  | 2 | 0 | 0 |
| 489 | `ProcessDefTemplate` |  | 23 | 0 | 0 |
| 490 | `ProcessDefTemplateCmItem` |  | 7 | 0 | 0 |
| 491 | `ProcessModuleAccessRight` |  | 9 | 0 | 0 |
| 492 | `ProcessModuleContainer` |  | 4 | 0 | 0 |
| 493 | `ProcessModuleDefinition` |  | 7 | 0 | 0 |
| 494 | `ProcessSubstituteDefinition` |  | 11 | 0 | 0 |
| 495 | `ProcessTemplate` |  | 6 | 0 | 0 |
| 496 | `ProcessTemplateEntity` |  | 3 | 0 | 0 |
| 497 | `QBizModel` |  | 8 | 0 | 0 |
| 498 | `QExtDataType` |  | 6 | 0 | 0 |
| 499 | `QServiceConfig` |  | 2 | 0 | 0 |
| 500 | `RDBDataSource` |  | 4 | 0 | 0 |
| 501 | `ReadingRecord` |  | 11 | 0 | 0 |
| 502 | `RefBizModel` |  | 7 | 0 | 0 |
| 503 | `RefContainer_ProcessInst` |  | 2 | 0 | 0 |
| 504 | `RefUserTask` |  | 4 | 0 | 0 |
| 505 | `RelatedUnit` |  | 5 | 0 | 0 |
| 506 | `Relationship` |  | 6 | 0 | 0 |
| 507 | `ReportDefinition` |  | 12 | 0 | 0 |
| 508 | `ReportDesignerDefinition` |  | 7 | 0 | 0 |
| 509 | `ReportUploadDefinition` |  | 5 | 0 | 0 |
| 510 | `Resignation` |  | 4 | 0 | 0 |
| 511 | `Resources` |  | 5 | 0 | 0 |
| 512 | `RestfulApplication` |  | 10 | 0 | 0 |
| 513 | `Role` |  | 5 | 0 | 0 |
| 514 | `RoleDefinition` |  | 6 | 0 | 0 |
| 515 | `RsrcBundle` |  | 4 | 0 | 0 |
| 516 | `RsrcBundleValue` |  | 9 | 0 | 0 |
| 517 | `RuntimePlatform` |  | 6 | 0 | 0 |
| 518 | `SYN_DeployDocServer` |  | 4 | 0 | 1 |
| 519 | `SYN_ExtFuncDef` |  | 1 | 0 | 0 |
| 520 | `SYN_ExtFuncLevel` |  | 2 | 0 | 0 |
| 521 | `SYN_ExtOrg` |  | 6 | 0 | 0 |
| 522 | `SYN_ExtPartJob` |  | 5 | 0 | 0 |
| 523 | `SYN_ExtUnitLevel` |  | 2 | 0 | 0 |
| 524 | `SYN_ExtUser` |  | 14 | 0 | 0 |
| 525 | `SYN_FunctionDefinition` |  | 3 | 0 | 1 |
| 526 | `SYN_FunctionLevel` |  | 4 | 0 | 0 |
| 527 | `SYN_Group_User` |  | 4 | 0 | 0 |
| 528 | `SYN_Groups` |  | 4 | 0 | 0 |
| 529 | `SYN_ISOAccessRight` |  | 3 | 0 | 1 |
| 530 | `SYN_ISOClause` |  | 4 | 0 | 1 |
| 531 | `SYN_ISODocCatergory` |  | 3 | 0 | 1 |
| 532 | `SYN_ISODocCmItem` |  | 11 | 0 | 0 |
| 533 | `SYN_ISODocTypeLevel` |  | 4 | 0 | 1 |
| 534 | `SYN_ISODocument` |  | 18 | 0 | 1 |
| 535 | `SYN_ISODocument_RelatedUnit` |  | 6 | 0 | 1 |
| 536 | `SYN_ISOFile` |  | 5 | 0 | 1 |
| 537 | `SYN_Role` |  | 5 | 0 | 0 |
| 538 | `SYN_RoleDefinition` |  | 3 | 0 | 1 |
| 539 | `SYN_Title` |  | 5 | 0 | 0 |
| 540 | `SYN_TitleDefinition` |  | 3 | 0 | 1 |
| 541 | `SYN_TrinityBelongDept` |  | 3 | 0 | 0 |
| 542 | `SYN_UnitLevel` |  | 4 | 0 | 0 |
| 543 | `SapConnection` |  | 7 | 0 | 0 |
| 544 | `SapFormMapping` |  | 7 | 0 | 0 |
| 545 | `SaveAsTemp` |  | 9 | 0 | 0 |
| 546 | `SchemaType` |  | 5 | 0 | 0 |
| 547 | `ScriptDefinition` |  | 5 | 0 | 0 |
| 548 | `ScriptingApplication` |  | 10 | 0 | 0 |
| 549 | `SecudocxSetting` |  | 7 | 0 | 0 |
| 550 | `SecurityLevel` |  | 6 | 0 | 0 |
| 551 | `Server2FavoriteMenu` |  | 7 | 0 | 0 |
| 552 | `Server2FavoriteProcess` |  | 5 | 0 | 0 |
| 553 | `Server2NoticeWorkItem` |  | 11 | 0 | 0 |
| 554 | `Server2PackageInvokeAuthority` |  | 6 | 0 | 0 |
| 555 | `Server2ProcessDefinition` |  | 28 | 0 | 0 |
| 556 | `Server2ProcessDefinitionHeader` |  | 11 | 0 | 0 |
| 557 | `Server2ProcessPackage` |  | 17 | 0 | 0 |
| 558 | `Server2ProcessPackageCategory` |  | 3 | 0 | 0 |
| 559 | `Server2ProcessPackageCmItem` |  | 8 | 0 | 0 |
| 560 | `Server2ProcessPackageHeader` |  | 9 | 0 | 0 |
| 561 | `Server2ProcessPkg_ProcessDef` |  | 2 | 0 | 0 |
| 562 | `Server2RedefinableHeader` |  | 7 | 0 | 0 |
| 563 | `Server2ToDoWorkItem` |  | 10 | 0 | 0 |
| 564 | `SimulationInformation` |  | 5 | 0 | 0 |
| 565 | `StrategyAssignInstance` |  | 3 | 0 | 0 |
| 566 | `SysTiptopMappingKey` |  | 20 | 0 | 0 |
| 567 | `SysintegrationServer` |  | 17 | 0 | 0 |
| 568 | `SysintegrationUsers` |  | 8 | 0 | 0 |
| 569 | `TFANotVerifylist` |  | 3 | 0 | 0 |
| 570 | `TFATrustDevice` |  | 8 | 0 | 0 |
| 571 | `TFAuthentication` |  | 6 | 0 | 0 |
| 572 | `TIMERS` |  | 6 | 0 | 0 |
| 573 | `TemplateGenMappingData` |  | 8 | 0 | 0 |
| 574 | `TimerWorkSchedule` |  | 7 | 0 | 0 |
| 575 | `Title` |  | 5 | 0 | 0 |
| 576 | `TitleDefinition` |  | 6 | 0 | 0 |
| 577 | `TrmCompanyMapping` |  | 10 | 0 | 0 |
| 578 | `TrmConversionFunction` |  | 10 | 0 | 0 |
| 579 | `TrmConversionFunctionData` |  | 10 | 0 | 0 |
| 580 | `TrmInitiateProcessProfile` |  | 12 | 0 | 0 |
| 581 | `TrmInitiateRecord` |  | 17 | 0 | 0 |
| 582 | `TypeDefinition` |  | 8 | 0 | 0 |
| 583 | `VettingType` |  | 11 | 0 | 0 |
| 584 | `VipUsers` |  | 1 | 0 | 0 |
| 585 | `WFRequestRecordModel` |  | 15 | 0 | 0 |
| 586 | `WatermarkAllowedForm` |  | 4 | 0 | 0 |
| 587 | `WordReportMapping` |  | 14 | 0 | 0 |
| 588 | `WorkCalendar` |  | 7 | 0 | 0 |
| 589 | `WorkingHour` |  | 6 | 0 | 0 |
| 590 | `WrapBamActInstData` |  | 17 | 0 | 0 |
| 591 | `WrapBamProInstData` |  | 22 | 0 | 0 |
| 592 | `WrapBamWorkAssignmentData` |  | 23 | 0 | 0 |
| 593 | `WrapBamWorkItemData` |  | 24 | 0 | 0 |
| 594 | `WriteBackRecord` |  | 6 | 0 | 0 |
| 595 | `XpressionDefinition` |  | 4 | 0 | 0 |
| 596 | `aapt120__aapt120` |  | 67 | 0 | 0 |
| 597 | `aapt120__s_apb` |  | 23 | 0 | 0 |
| 598 | `cgexpense` |  | 18 | 0 | 0 |
| 599 | `cgexpense_detail` |  | 9 | 0 | 0 |
| 600 | `cgsuggest__cgsuggest` |  | 36 | 0 | 0 |
| 601 | `ecp_anc_info` |  | 26 | 0 | 0 |
| 602 | `ecp_anc_range` |  | 11 | 0 | 0 |
| 603 | `ecp_anc_type` |  | 13 | 0 | 0 |
| 604 | `ecp_anc_type_range` |  | 11 | 0 | 0 |
| 605 | `ecp_anc_view_record` |  | 5 | 0 | 0 |
| 606 | `ecp_attachment` |  | 18 | 0 | 0 |
| 607 | `ecp_chart` |  | 27 | 0 | 0 |
| 608 | `ecp_chart_range` |  | 11 | 0 | 0 |
| 609 | `ecp_link` |  | 21 | 0 | 0 |
| 610 | `ecp_product` |  | 19 | 0 | 0 |
| 611 | `ecp_schedule` |  | 24 | 0 | 0 |
| 612 | `ecp_schedule_range` |  | 15 | 0 | 0 |
| 613 | `ecp_schedule_type` |  | 13 | 0 | 0 |
| 614 | `ecp_schedule_type_range` |  | 12 | 0 | 0 |
| 615 | `ecp_schedule_type_relation` |  | 9 | 0 | 0 |
| 616 | `ecp_source_connect` |  | 15 | 0 | 0 |
| 617 | `ecp_tool_dl` |  | 18 | 0 | 0 |

## 5. Column 清單（依領域分群、表內依估計列數排序）


### 前綴 `Cha` — 簽核/變更（17 表）


#### `ChangeActivityStateAudit` — （無中文名）　(列數約 2,145,583)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `aboveProcessInstanceOID` |  | nchar(32) | Y |  |
| `createdTime` |  | datetime | N |  |
| `currentProcessInstanceState` |  | int | N |  |
| `currentProcessInstanceOID` |  | nchar(32) | N |  |
| `sourceOID` |  | nchar(32) | Y |  |
| `currentActivityDefinitionName` |  | nvarchar(100) | Y |  |
| `newState` |  | int | N |  |
| `objectVersion` |  | int | N |  |
| `oldState` |  | int | N |  |

#### `ChangeWorkItemStateAudit` — （無中文名）　(列數約 1,427,104)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `aboveProcessInstanceOID` |  | nchar(32) | Y |  |
| `createdTime` |  | datetime | N |  |
| `currentProcessInstanceState` |  | int | N |  |
| `currentProcessInstanceOID` |  | nchar(32) | N |  |
| `currentActivityInstanceOID` |  | nchar(32) | N |  |
| `sourceOID` |  | nchar(32) | N |  |
| `newState` |  | int | N |  |
| `objectVersion` |  | int | N |  |
| `oldState` |  | int | N |  |

#### `ChangeProcessStateAudit` — （無中文名）　(列數約 301,626)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `aboveProcessInstanceOID` |  | nchar(32) | Y |  |
| `createdTime` |  | datetime | N |  |
| `currentProcessInstanceState` |  | int | N |  |
| `sourceOID` |  | nchar(32) | N |  |
| `newState` |  | int | N |  |
| `objectVersion` |  | int | N |  |
| `oldState` |  | int | N |  |

#### `ChatFileProperties` — （無中文名）　(列數約 22)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `paraKey` |  | nvarchar(256) | Y |  |
| `paraValue` |  | nvarchar(2000) | Y |  |
| `description` |  | nvarchar(2000) | Y |  |
| `objectVersion` |  | int | Y |  |
| `createdTime` |  | datetime | Y |  |
| `creatorOID` |  | nvarchar(32) | Y |  |
| `updatedTime` |  | datetime | Y |  |
| `updaterOID` |  | nvarchar(32) | Y |  |

#### `ChatFileAssistedReading` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `processDefinitionId` |  | nvarchar(100) | Y |  |
| `objectVersion` |  | int | Y |  |
| `createdTime` |  | datetime | Y |  |
| `creatorOID` |  | nvarchar(32) | Y |  |
| `updatedTime` |  | datetime | Y |  |
| `updaterOID` |  | nvarchar(32) | Y |  |

#### `ChatFileExecutionRecord` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `experienceOID` |  | nchar(32) | Y |  |
| `formSerialNumber` |  | nvarchar(100) | Y |  |
| `closedTime` |  | datetime | Y |  |
| `conditionRule` |  | ntext | Y |  |
| `isComplyRule` |  | nvarchar(1) | Y |  |
| `objectVersion` |  | int | Y |  |
| `createdTime` |  | datetime | Y |  |
| `creatorOID` |  | nvarchar(32) | Y |  |
| `updatedTime` |  | datetime | Y |  |
| `updaterOID` |  | nvarchar(32) | Y |  |

#### `ChatFileExperience` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `processDefinitionId` |  | nvarchar(100) | Y |  |
| `formDefinitionId` |  | nvarchar(100) | Y |  |
| `startDate` |  | datetime | Y |  |
| `endDate` |  | datetime | Y |  |
| `timeFrame` |  | int | Y |  |
| `conditionRule` |  | nvarchar(max) | Y |  |
| `objectVersion` |  | int | Y |  |
| `createdTime` |  | datetime | Y |  |
| `creatorOID` |  | nvarchar(32) | Y |  |
| `updatedTime` |  | datetime | Y |  |
| `updaterOID` |  | nvarchar(32) | Y |  |

#### `ChatFileExperienceRecords` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `actionType` |  | nchar(1) | Y |  |
| `executionStatus` |  | nchar(1) | Y |  |
| `type` |  | nchar(1) | Y |  |
| `processDefinitionId` |  | nvarchar(100) | Y |  |
| `processSerialNumber` |  | nvarchar(100) | Y |  |
| `formDefinitionId` |  | nvarchar(100) | Y |  |
| `formVersion` |  | int | Y |  |
| `formSerialNumber` |  | nvarchar(100) | Y |  |
| `noCmDocumentOID` |  | nchar(32) | Y |  |
| `fileName` |  | nvarchar(100) | Y |  |
| `fileCreatedTime` |  | datetime | Y |  |
| `scheduleStartTime` |  | datetime | Y |  |
| `completedTime` |  | datetime | Y |  |
| `apiRequest` |  | nvarchar(max) | Y |  |
| `dmcId` |  | nvarchar(60) | Y |  |
| `fileId` |  | nvarchar(60) | Y |  |
| `classificationNo` |  | nvarchar(60) | Y |  |
| `apiResponse` |  | nvarchar(max) | Y |  |
| `objectVersion` |  | int | Y |  |
| `createdTime` |  | datetime | Y |  |
| `creatorOID` |  | nvarchar(32) | Y |  |
| `updatedTime` |  | datetime | Y |  |
| `updaterOID` |  | nvarchar(32) | Y |  |

#### `ChatFileExperienceSchedule` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `mainIsEnable` |  | nvarchar(10) | Y |  |
| `week` |  | int | Y |  |
| `isEnable` |  | nvarchar(10) | Y |  |
| `executionInterval` |  | ntext | Y |  |
| `jobName` |  | nvarchar(64) | Y |  |
| `jobGroupName` |  | nvarchar(64) | Y |  |
| `triggerName` |  | nvarchar(64) | Y |  |
| `triggerGroupName` |  | nvarchar(64) | Y |  |
| `objectVersion` |  | int | Y |  |
| `createdTime` |  | datetime | Y |  |
| `creatorOID` |  | nvarchar(32) | Y |  |
| `updatedTime` |  | datetime | Y |  |
| `updaterOID` |  | nvarchar(32) | Y |  |

#### `ChatFileISOTransferRecords` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `actionType` |  | nchar(1) | Y |  |
| `executionStatus` |  | nchar(1) | Y |  |
| `type` |  | nchar(1) | Y |  |
| `docNo` |  | nvarchar(100) | Y | FK? |
| `docName` |  | nvarchar(255) | Y |  |
| `documentVersion` |  | int | Y |  |
| `noCmDocumentOID` |  | nchar(32) | Y |  |
| `kCategoryOID` |  | nchar(32) | Y |  |
| `fileName` |  | nvarchar(100) | Y |  |
| `fileCreatedTime` |  | datetime | Y |  |
| `scheduleStartTime` |  | datetime | Y |  |
| `completedTime` |  | datetime | Y |  |
| `apiRequest` |  | nvarchar(max) | Y |  |
| `dmcId` |  | nvarchar(60) | Y |  |
| `fileId` |  | nvarchar(60) | Y |  |
| `classificationNo` |  | nvarchar(60) | Y |  |
| `apiResponse` |  | nvarchar(max) | Y |  |
| `objectVersion` |  | int | Y |  |
| `createdTime` |  | datetime | Y |  |
| `creatorOID` |  | nvarchar(32) | Y |  |
| `updatedTime` |  | datetime | Y |  |
| `updaterOID` |  | nvarchar(32) | Y |  |

> 隱含關聯：[隱含FK→ docNo→SYN_ISODocCmItem]

#### `ChatFileKnowledge` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `kCategoryOID` |  | nchar(32) | Y |  |
| `docNo` |  | nvarchar(100) | Y | FK? |
| `docName` |  | nvarchar(255) | Y |  |
| `nextTimeEnabled` |  | nvarchar(1) | Y |  |
| `nextTimeCategory` |  | nvarchar(32) | Y |  |
| `objectVersion` |  | int | Y |  |
| `createdTime` |  | datetime | Y |  |
| `creatorOID` |  | nvarchar(32) | Y |  |
| `updatedTime` |  | datetime | Y |  |
| `updaterOID` |  | nvarchar(32) | Y |  |

> 隱含關聯：[隱含FK→ docNo→SYN_ISODocCmItem]

#### `ChatFileKnowledgeCategory` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `name` |  | nvarchar(100) | Y |  |
| `objectVersion` |  | int | Y |  |
| `createdTime` |  | datetime | Y |  |
| `creatorOID` |  | nvarchar(32) | Y |  |
| `updatedTime` |  | datetime | Y |  |
| `updaterOID` |  | nvarchar(32) | Y |  |

#### `ChatFilePresetProblem` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `experienceOID` |  | nchar(32) | Y |  |
| `formDefinitionId` |  | nvarchar(100) | Y |  |
| `sort` |  | int | Y |  |
| `question` |  | ntext | Y |  |
| `objectVersion` |  | int | Y |  |
| `createdTime` |  | datetime | Y |  |
| `creatorOID` |  | nvarchar(32) | Y |  |
| `updatedTime` |  | datetime | Y |  |
| `updaterOID` |  | nvarchar(32) | Y |  |

#### `ChatFileQARecord` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `userId` |  | nvarchar(60) | Y |  |
| `sceneType` |  | nchar(1) | Y |  |
| `processDefinitionId` |  | nvarchar(100) | Y |  |
| `processSerialNumber` |  | nvarchar(100) | Y |  |
| `requestTime` |  | datetime | Y |  |
| `requestData` |  | nvarchar(max) | Y |  |
| `reponseTime` |  | datetime | Y |  |
| `reponseData` |  | nvarchar(max) | Y |  |
| `objectVersion` |  | int | Y |  |
| `createdTime` |  | datetime | Y |  |
| `creatorOID` |  | nvarchar(32) | Y |  |
| `updatedTime` |  | datetime | Y |  |
| `updaterOID` |  | nvarchar(32) | Y |  |

#### `ChatFileTransferRecords` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `actionType` |  | nchar(1) | Y |  |
| `executionStatus` |  | nchar(1) | Y |  |
| `type` |  | nchar(1) | Y |  |
| `processDefinitionId` |  | nvarchar(100) | Y |  |
| `processSerialNumber` |  | nvarchar(100) | Y |  |
| `noCmDocumentOID` |  | nchar(32) | Y |  |
| `ISODocMainIndex` |  | bigint | Y |  |
| `ISOTypeOID` |  | nchar(32) | Y |  |
| `fileName` |  | nvarchar(100) | Y |  |
| `fileCreatedTime` |  | datetime | Y |  |
| `scheduleStartTime` |  | datetime | Y |  |
| `completedTime` |  | datetime | Y |  |
| `apiRequest` |  | nvarchar(max) | Y |  |
| `dmcId` |  | nvarchar(60) | Y |  |
| `fileId` |  | nvarchar(60) | Y |  |
| `classificationNo` |  | nvarchar(60) | Y |  |
| `apiResponse` |  | nvarchar(max) | Y |  |
| `objectVersion` |  | int | Y |  |
| `createdTime` |  | datetime | Y |  |
| `creatorOID` |  | nvarchar(32) | Y |  |
| `updatedTime` |  | datetime | Y |  |
| `updaterOID` |  | nvarchar(32) | Y |  |

#### `ChatFileUserManagement` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `userOID` |  | nvarchar(32) | Y |  |
| `enable` |  | int | Y |  |
| `objectVersion` |  | int | Y |  |
| `createdTime` |  | datetime | Y |  |
| `creatorOID` |  | nvarchar(32) | Y |  |
| `updatedTime` |  | datetime | Y |  |
| `updaterOID` |  | nvarchar(32) | Y |  |

#### `ChatFileUserToken` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `loginId` |  | nvarchar(255) | Y |  |
| `token` |  | nvarchar(60) | Y |  |
| `tokenCreateTime` |  | datetime | Y |  |
| `tokenValidTime` |  | bigint | Y |  |
| `objectVersion` |  | int | Y |  |
| `createdTime` |  | datetime | Y |  |
| `creatorOID` |  | nvarchar(32) | Y |  |
| `updatedTime` |  | datetime | Y |  |
| `updaterOID` |  | nvarchar(32) | Y |  |

### 前綴 `Wor` — 工作流(Workflow)（8 表）


#### `WorkStep` — （無中文名）　(列數約 717,258)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `currentState` |  | int | N |  |
| `definitionId` |  | nvarchar(100) | N |  |
| `containerOID` |  | nchar(32) | N |  |
| `objectVersion` |  | int | N |  |
| `contextOID` |  | nchar(32) | N |  |
| `exceptionHandleDefIndex` |  | int | Y |  |
| `nextExceptionHandleTime` |  | datetime | Y |  |
| `numOfExceptionHandle` |  | int | Y |  |
| `workStepIndex` |  | int | N |  |

#### `WorkItem` — （無中文名）　(列數約 716,995)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `workItemName` |  | nvarchar(100) | Y |  |
| `currentState` |  | int | N |  |
| `dispatchType` |  | int | Y |  |
| `executiveComment` |  | ntext | Y |  |
| `createdTime` |  | datetime | N |  |
| `completedTime` |  | datetime | Y |  |
| `objectVersion` |  | int | N |  |
| `description` |  | ntext | Y |  |
| `containerOID` |  | nchar(32) | N |  |
| `contextOID` |  | nchar(32) | N |  |
| `performerOID` |  | nchar(32) | Y |  |
| `reexecActivityInstOID` |  | nchar(32) | Y |  |
| `limits` |  | int | N |  |
| `signedComment` |  | ntext | Y |  |
| `ownerOID` |  | nchar(32) | Y |  |
| `bypassPerformerOID` |  | nchar(32) | Y |  |
| `signoffState` |  | int | N |  |
| `isAccessMcloud` |  | int | Y |  |
| `skipUserName` |  | nvarchar(32) | Y |  |
| `attachmentHits` |  | nvarchar(4000) | Y |  |
| `reminder` |  | int | Y |  |
| `clientIP` |  | nvarchar(100) | Y |  |
| `validateModeOperate` |  | int | Y |  |
| `asyncMessage` |  | nvarchar(2000) | Y |  |
| `signedTime` |  | datetime | Y |  |

#### `WorkAssignment` — （無中文名）　(列數約 86,991)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `workItemOID` |  | nchar(32) | Y |  |
| `assigneeOID` |  | nchar(32) | N |  |
| `assignmentType` |  | int | N |  |
| `isNotice` |  | int | N |  |
| `noticeType` |  | int | Y |  |
| `viewTimes` |  | int | N |  |
| `assigneePriority` |  | int | Y |  |
| `notificationReason` |  | nvarchar(2000) | Y |  |
| `notificationSenderOID` |  | nchar(32) | Y |  |

#### `WorkAssignment_Label` — （無中文名）　(列數約 15,433)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `WorkAssignmentOID` |  | nchar(32) | N | PK |
| `LabelOID` |  | nchar(32) | N | PK |

#### `WorkflowServer` — （無中文名）　(列數約 7)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `id` |  | nvarchar(50) | N |  |
| `appServerAddress` |  | nvarchar(50) | N |  |
| `webServerAddress` |  | nvarchar(50) | N |  |
| `containerOID` |  | nchar(32) | Y |  |
| `isDefault` |  | int | N |  |
| `defaultDocServerOID` |  | nchar(32) | N |  |
| `intranetWebServerAddress` |  | nvarchar(50) | Y |  |

#### `WordReportMapping` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `formMapping` |  | ntext | Y |  |
| `fileName` |  | ntext | Y |  |
| `isPrintLogo` |  | int | Y |  |
| `isPrintApprove` |  | int | Y |  |
| `isOptimizeShow` |  | int | Y |  |
| `isPrintStampOID` |  | nchar(32) | Y |  |
| `outputType` |  | int | Y |  |
| `reportMode` |  | int | Y |  |
| `objectVersion` |  | int | Y |  |
| `createdTime` |  | datetime | Y |  |
| `creatorOID` |  | nvarchar(32) | Y |  |
| `updatedTime` |  | datetime | Y |  |
| `updaterOID` |  | nvarchar(32) | Y |  |

#### `WorkCalendar` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `containerOID` |  | nchar(32) | Y |  |
| `description` |  | ntext | Y |  |
| `calendarName` |  | nvarchar(100) | N |  |
| `shortName` |  | nvarchar(100) | Y |  |
| `isDefaultCalendar` |  | int | Y |  |

#### `WorkingHour` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `containerOID` |  | nchar(32) | Y |  |
| `endTime` |  | datetime | N |  |
| `startTime` |  | datetime | N |  |
| `itemOrder` |  | int | N |  |

### 前綴 `Par` — —（5 表）


#### `ParticipantActivityInstance` — （無中文名）　(列數約 713,005)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `addingActivityAuthority` |  | int | N |  |
| `ableToInvokeRefProcess` |  | int | N |  |
| `ableToAskActivityReexecute` |  | int | N |  |
| `bypassed` |  | int | N |  |
| `bypassable` |  | int | N |  |
| `batchPerformable` |  | int | N |  |
| `containerOID` |  | nchar(32) | N |  |
| `contextOID` |  | nchar(32) | N |  |
| `currentState` |  | int | N |  |
| `comeBackActivityInstOID` |  | nchar(32) | Y |  |
| `createdTime` |  | datetime | N |  |
| `definitionId` |  | nvarchar(100) | N |  |
| `numOfNotification` |  | int | N |  |
| `noticeAuthority` |  | int | N |  |
| `reassignable` |  | int | N |  |
| `requiredToSpecifyOrgUnit` |  | int | N |  |
| `secured` |  | int | N |  |
| `terminateReason` |  | int | Y |  |
| `objectVersion` |  | int | N |  |
| `performType` |  | nvarchar(50) | N |  |
| `lastNoticeTime` |  | datetime | Y |  |
| `isAccessMcloud` |  | int | Y |  |
| `automaticBypassed` |  | int | N |  |
| `container1OID` |  | nchar(32) | Y |  |
| `container2OID` |  | nchar(32) | Y |  |
| `redoRefActivityInstOID` |  | nchar(32) | Y |  |

#### `ParticipantDefinition` — （無中文名）　(列數約 340,322)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `containerOID` |  | nchar(32) | Y |  |
| `description` |  | ntext | Y |  |
| `externalReferenceOID` |  | nchar(32) | Y |  |
| `id` |  | nvarchar(100) | N |  |
| `participantDefinitionName` |  | nvarchar(100) | Y |  |
| `objectVersion` |  | int | N |  |
| `participantType` |  | nvarchar(50) | N |  |
| `includeSubUnit` |  | int | N |  |
| `organizationUnitId` |  | nvarchar(100) | Y |  |
| `resourceId` |  | nvarchar(100) | Y |  |
| `employeeId` |  | nvarchar(100) | Y |  |
| `groupId` |  | nvarchar(100) | Y |  |
| `activityDefinitionId` |  | nvarchar(100) | Y |  |
| `functionDefinitionName` |  | nvarchar(100) | Y |  |
| `titleDefinitionName` |  | nvarchar(100) | Y |  |
| `roleDefinitionName` |  | nvarchar(100) | Y |  |
| `relationshipName` |  | nvarchar(100) | Y |  |
| `organizationUnitPropertyName` |  | nvarchar(100) | Y |  |
| `autoAgentId` |  | nvarchar(100) | Y |  |
| `strategyAssignDefinitionOID` |  | nchar(32) | Y |  |
| `formFieldId` |  | nvarchar(255) | Y |  |
| `organizationId` |  | nvarchar(100) | Y |  |
| `organizationUnitType` |  | int | Y |  |
| `processVariableId` |  | nvarchar(255) | Y |  |

#### `ParticipantDefinition2` — （無中文名）　(列數約 333,533)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | char(32) | N |  |
| `containerOID` |  | char(32) | N |  |
| `description` |  | ntext | Y |  |
| `externalReferenceOID` |  | char(32) | Y |  |
| `id` |  | nvarchar(100) | N |  |
| `participantDefinitionName` |  | nvarchar(100) | Y |  |
| `objectVersion` |  | int | N |  |
| `participantType` |  | nvarchar(50) | N |  |
| `includeSubUnit` |  | int | N |  |
| `organizationUnitId` |  | nvarchar(100) | Y |  |
| `resourceId` |  | nvarchar(100) | Y |  |
| `employeeId` |  | nvarchar(100) | Y |  |
| `groupId` |  | nvarchar(100) | Y |  |
| `activityDefinitionId` |  | nvarchar(100) | Y |  |
| `functionDefinitionName` |  | nvarchar(100) | Y |  |
| `titleDefinitionName` |  | nvarchar(100) | Y |  |
| `roleDefinitionName` |  | nvarchar(100) | Y |  |
| `relationshipName` |  | nvarchar(100) | Y |  |
| `organizationUnitPropertyName` |  | nvarchar(100) | Y |  |
| `autoAgentId` |  | nvarchar(100) | Y |  |
| `strategyAssignDefinitionOID` |  | char(32) | Y |  |
| `formFieldId` |  | nvarchar(255) | Y |  |
| `organizationId` |  | nvarchar(100) | Y |  |
| `organizationUnitType` |  | int | Y |  |
| `processVariableId` |  | nvarchar(255) | Y |  |

#### `ParticularRecord` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `containerOID` |  | nchar(32) | Y |  |
| `description` |  | ntext | Y |  |
| `isAbsence` |  | int | N |  |
| `particularDay` |  | datetime | N |  |

#### `ParticularRule` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `containerOID` |  | nchar(32) | Y |  |
| `description` |  | ntext | Y |  |
| `applyEnd` |  | datetime | N |  |
| `applyStart` |  | datetime | N |  |
| `dayOrderPerWeek` |  | int | N |  |
| `isVacation` |  | int | N |  |
| `weekOrderPerMonth` |  | int | N |  |

### 前綴 `Tra` — —（3 表）


#### `TransitionRestriction` — （無中文名）　(列數約 431,679)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `containerOID` |  | nchar(32) | Y |  |
| `objectVersion` |  | int | N |  |
| `joinType` |  | nvarchar(50) | Y |  |
| `splitType` |  | nvarchar(50) | Y |  |

#### `TransitionReference` — （無中文名）　(列數約 417,002)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `transitionDefinitionId` |  | nvarchar(100) | N |  |
| `objectVersion` |  | int | N |  |
| `containerOID` |  | nchar(32) | Y |  |

#### `TransitionDefinition` — （無中文名）　(列數約 416,665)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `id` |  | nvarchar(100) | N |  |
| `transitionDefinitionName` |  | nvarchar(100) | Y |  |
| `conditionOID` |  | nchar(32) | Y |  |
| `containerOID` |  | nchar(32) | Y |  |
| `description` |  | ntext | Y |  |
| `fromActivityDefinitionId` |  | nvarchar(100) | N |  |
| `objectVersion` |  | int | N |  |
| `toActivityDefinitionId` |  | nvarchar(100) | N |  |

### 前綴 `Act` — 活動(Activity)（5 表）


#### `ActivityDefinition` — （無中文名）　(列數約 431,679)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `activityDefinitionName` |  | nvarchar(100) | Y |  |
| `activityTypeOID` |  | nchar(32) | N |  |
| `addingActivityAuthority` |  | int | N |  |
| `ableToInvokeRefProcess` |  | int | N |  |
| `ableToAskActivityReexecute` |  | int | N |  |
| `bypassable` |  | int | N |  |
| `batchPerformable` |  | int | N |  |
| `containerOID` |  | nchar(32) | Y |  |
| `description` |  | ntext | Y |  |
| `documentation` |  | nvarchar(100) | Y |  |
| `icon` |  | nvarchar(100) | Y |  |
| `id` |  | nvarchar(100) | N |  |
| `limits` |  | real | Y |  |
| `noticeAuthority` |  | int | N |  |
| `reassignable` |  | int | N |  |
| `requiredToSpecifyOrgUnit` |  | int | N |  |
| `performerIds` |  | ntext | Y |  |
| `priority` |  | nvarchar(50) | Y |  |
| `secured` |  | int | N |  |
| `simulationInformationOID` |  | nchar(32) | Y |  |
| `objectVersion` |  | int | N |  |
| `applyDefaultNoticeContent` |  | int | N |  |
| `startMode` |  | nvarchar(50) | N |  |
| `finishMode` |  | nvarchar(50) | N |  |
| `finishWorkPercentage` |  | real | N |  |
| `multiUserMode` |  | nvarchar(50) | N |  |
| `processRole` |  | nvarchar(100) | Y |  |
| `decisionRuleListOID` |  | nchar(32) | Y |  |
| `boundViewInformationOID` |  | nchar(32) | Y |  |
| `formFieldAccessDefinitionOID` |  | nchar(32) | Y |  |
| `dealOvertimeActivityType` |  | nvarchar(50) | N |  |
| `performType` |  | nvarchar(50) | N |  |
| `multiNotificationIntervalTime` |  | int | N |  |
| `notificationIntervalTimeUnit` |  | nvarchar(50) | N |  |
| `multiNotification` |  | int | N |  |
| `regainable` |  | int | N |  |
| `requiredToTransForm` |  | int | N |  |
| `unReexcuteActIds` |  | ntext | Y |  |
| `unReexecuteType` |  | nvarchar(50) | N |  |
| `responsible` |  | int | Y |  |
| `unitManager` |  | int | Y |  |
| `disNoticeSend` |  | int | Y |  |
| `proInsLevel` |  | int | N |  |
| `printActivity` |  | int | N |  |
| `autoDelivery` |  | int | N |  |
| `automaticPhrase` |  | nvarchar(100) | Y |  |
| `firstNoticeUnitManager` |  | int | Y |  |
| `firstNoticeInitiator` |  | int | Y |  |
| `firstNoticeResponsible` |  | int | Y |  |
| `secondNoticeUnitManager` |  | int | Y |  |
| `secondNoticeInitiator` |  | int | Y |  |
| `secondNoticeResponsible` |  | int | Y |  |
| `thirdNoticeUnitManager` |  | int | Y |  |
| `thirdNoticeInitiator` |  | int | Y |  |
| `thirdNoticeResponsible` |  | int | Y |  |
| `notificationAttachment` |  | int | N |  |
| `reexecuteComm` |  | int | N |  |
| `batchComm` |  | int | N |  |
| `confirmAttachmentHits` |  | int | N |  |
| `bpmnType` |  | nvarchar(30) | Y |  |
| `straightSignOff` |  | int | Y |  |
| `confirmComm` |  | int | Y |  |
| `addCustomWorkItemOID` |  | nchar(32) | Y |  |
| `mustUploadAttachment` |  | int | Y |  |
| `disNoticeSendForSendTask` |  | int | Y |  |
| `disNoticeSendForReexecute` |  | int | Y |  |
| `disNoticeSendForRegainable` |  | int | Y |  |
| `allowChangeOnlineRead` |  | int | Y |  |

#### `ActivityNotification` — （無中文名）　(列數約 370,754)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `activityInstanceOID` |  | nchar(32) | Y |  |
| `subject` |  | ntext | Y |  |
| `message` |  | ntext | Y |  |
| `activityNotificationType` |  | int | N |  |
| `receiverOID` |  | nchar(32) | N |  |
| `createdTime` |  | datetime | N |  |

#### `ActualParameter` — （無中文名）　(列數約 96,030)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `containerOID` |  | nchar(32) | Y |  |
| `objectVersion` |  | int | N |  |
| `relevantDataDefinitionId` |  | nvarchar(100) | N |  |

#### `ActivitySetDefinition` — （無中文名）　(列數約 45,768)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `containerOID` |  | nchar(32) | Y |  |
| `objectVersion` |  | int | N |  |
| `id` |  | nvarchar(100) | N |  |

#### `ActivityDefinitionEntity` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `entityId` |  | nvarchar(100) | N |  |
| `activityDefinitionName` |  | nvarchar(100) | Y |  |
| `activityTypeOID` |  | nchar(32) | N |  |
| `addingActivityAuthority` |  | int | N |  |
| `ableToInvokeRefProcess` |  | int | N |  |
| `ableToAskActivityReexecute` |  | int | N |  |
| `bypassable` |  | int | N |  |
| `batchPerformable` |  | int | N |  |
| `containerOID` |  | nchar(32) | Y |  |
| `description` |  | ntext | Y |  |
| `documentation` |  | nvarchar(100) | Y |  |
| `icon` |  | nvarchar(100) | Y |  |
| `id` |  | nvarchar(100) | N |  |
| `limits` |  | real | Y |  |
| `noticeAuthority` |  | int | N |  |
| `reassignable` |  | int | N |  |
| `requiredToSpecifyOrgUnit` |  | int | N |  |
| `performerIds` |  | ntext | Y |  |
| `priority` |  | nvarchar(50) | Y |  |
| `secured` |  | int | N |  |
| `simulationInformationOID` |  | nchar(32) | Y |  |
| `applyDefaultNoticeContent` |  | int | N |  |
| `startMode` |  | nvarchar(50) | N |  |
| `finishMode` |  | nvarchar(50) | N |  |
| `finishWorkPercentage` |  | real | N |  |
| `multiUserMode` |  | nvarchar(50) | N |  |
| `processRole` |  | nvarchar(100) | Y |  |
| `decisionRuleListOID` |  | nchar(32) | Y |  |
| `boundViewInformationOID` |  | nchar(32) | Y |  |
| `formFieldAccessDefinitionOID` |  | nchar(32) | Y |  |
| `dealOvertimeActivityType` |  | nvarchar(50) | N |  |
| `performType` |  | nvarchar(50) | N |  |
| `multiNotificationIntervalTime` |  | int | N |  |
| `notificationIntervalTimeUnit` |  | nvarchar(50) | N |  |
| `multiNotification` |  | int | N |  |
| `regainable` |  | int | N |  |
| `requiredToTransForm` |  | int | N |  |
| `unReexcuteActIds` |  | ntext | Y |  |
| `unReexecuteType` |  | nvarchar(50) | N |  |
| `responsible` |  | int | Y |  |
| `unitManager` |  | int | Y |  |
| `proInsLevel` |  | int | N |  |
| `printActivity` |  | int | N |  |
| `firstNoticeUnitManager` |  | int | Y |  |
| `firstNoticeInitiator` |  | int | Y |  |
| `firstNoticeResponsible` |  | int | Y |  |
| `secondNoticeUnitManager` |  | int | Y |  |
| `secondNoticeInitiator` |  | int | Y |  |
| `secondNoticeResponsible` |  | int | Y |  |
| `thirdNoticeUnitManager` |  | int | Y |  |
| `thirdNoticeInitiator` |  | int | Y |  |
| `thirdNoticeResponsible` |  | int | Y |  |
| `addCustomWorkItemOID` |  | nchar(32) | Y |  |
| `autoDelivery` |  | int | Y |  |
| `automaticPhrase` |  | nvarchar(100) | Y |  |
| `batchComm` |  | int | Y |  |
| `bpmnType` |  | nvarchar(30) | Y |  |
| `confirmAttachmentHits` |  | int | Y |  |
| `confirmComm` |  | int | Y |  |
| `notificationAttachment` |  | int | Y |  |
| `reexecuteComm` |  | int | Y |  |
| `straightSignOff` |  | int | Y |  |
| `mustUploadAttachment` |  | int | Y |  |
| `disNoticeSendForSendTask` |  | int | Y |  |
| `disNoticeSendForReexecute` |  | int | Y |  |
| `disNoticeSendForRegainable` |  | int | Y |  |
| `allowChangeOnlineRead` |  | int | Y |  |
| `disNoticeSend` |  | int | Y |  |

### 前綴 `Pro` — 流程(Process)（25 表）


#### `ProcessNotification` — （無中文名）　(列數約 153,507)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `processInstanceOID` |  | nchar(32) | N |  |
| `processSerialNumber` |  | nvarchar(100) | Y |  |
| `objectVersion` |  | int | N |  |
| `processNotificationType` |  | int | N |  |
| `subject` |  | ntext | Y |  |
| `message` |  | ntext | Y |  |
| `receiverOID` |  | nchar(32) | N |  |
| `createdTime` |  | datetime | N |  |
| `isView` |  | nvarchar(1) | Y |  |

#### `ProcessContext` — （無中文名）　(列數約 151,537)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `aboveProcessInstanceOID` |  | nchar(32) | Y |  |
| `containerOID` |  | nchar(32) | Y |  |
| `objectVersion` |  | int | N |  |
| `processPackageOID` |  | nchar(32) | Y |  |

#### `ProcessInstance` — （無中文名）　(列數約 151,497)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `contextOID` |  | nchar(32) | N |  |
| `currentState` |  | int | N |  |
| `invokeOrganizationUnitOID` |  | nchar(32) | N |  |
| `requesterOID` |  | nchar(32) | N |  |
| `serialNumber` |  | nvarchar(100) | Y |  |
| `isMain` |  | int | N |  |
| `createdTime` |  | datetime | N |  |
| `processInstanceName` |  | nvarchar(100) | Y |  |
| `processDefinitionId` |  | nvarchar(100) | N |  |
| `relationalManOID` |  | nchar(32) | N |  |
| `defaultAssignmentType` |  | int | N |  |
| `referContainerOID` |  | nchar(32) | Y |  |
| `numOfNotification` |  | int | N |  |
| `subject` |  | ntext | Y |  |
| `referOrganizationUnitOID` |  | nchar(32) | Y |  |
| `abortComment` |  | ntext | Y |  |
| `abortable` |  | int | N |  |
| `bundleContainer` |  | ntext | Y |  |
| `abortedManOID` |  | nchar(32) | Y |  |
| `abortedManType` |  | int | N |  |
| `insLevelOID` |  | nchar(32) | Y |  |
| `sysIntegratedWith` |  | int | N |  |
| `dueDate` |  | datetime | Y |  |
| `additionalRules` |  | int | N |  |
| `lastNoticeTime` |  | datetime | Y |  |
| `redefinableHeaderOID` |  | nchar(32) | Y |  |
| `mobilityProcess` |  | int | N |  |
| `processModel` |  | nchar(4) | Y |  |
| `isExistCritical` |  | int | Y |  |
| `mobilitySignOff` |  | int | Y |  |
| `requester1OID` |  | nchar(32) | Y |  |
| `requester2OID` |  | nchar(32) | Y |  |
| `fullSearchContent` |  | nvarchar(4000) | Y |  |
| `keyWords` |  | nvarchar(4000) | Y |  |

#### `ProcessDefinition` — （無中文名）　(列數約 48,092)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `accessLevel` |  | nvarchar(50) | N |  |
| `id` |  | nvarchar(100) | N |  |
| `headerOID` |  | nchar(32) | N |  |
| `processDefinitionName` |  | nvarchar(100) | Y |  |
| `objectVersion` |  | int | N |  |
| `redefinableHeaderOID` |  | nchar(32) | Y |  |
| `applyDefaultNoticeContent` |  | int | N |  |
| `relationManDefId` |  | nvarchar(100) | Y |  |
| `lastActivityIdNum` |  | int | N |  |
| `lastActivitySetIdNum` |  | int | N |  |
| `lastTransitionIdNum` |  | int | N |  |
| `lastParticipantIdNum` |  | int | N |  |
| `lastFormalParameterIdNum` |  | int | N |  |
| `allowCanceled` |  | int | N |  |
| `notificationIntervalTimeUnit` |  | nvarchar(50) | N |  |
| `multiNotificationIntervalTime` |  | int | N |  |
| `multiNotification` |  | int | N |  |
| `actionAfterAbortedOID` |  | nchar(32) | Y |  |
| `actionAfterTerminatedOID` |  | nchar(32) | Y |  |
| `actionAfterCompletedOID` |  | nchar(32) | Y |  |
| `processViewInformationOID` |  | nchar(32) | Y |  |
| `abortable` |  | int | N |  |
| `bundleContainer` |  | ntext | Y |  |
| `noticable` |  | int | N |  |
| `noticeAllAuthority` |  | int | N |  |
| `additionalRules` |  | int | N |  |
| `personalDataProtection` |  | int | Y |  |
| `mobilityProcess` |  | int | N |  |
| `bpmXML` |  | ntext | Y |  |
| `sysintegrationOID` |  | nchar(32) | Y |  |
| `mobilitySignOff` |  | int | Y |  |
| `deleteProcess` |  | int | Y |  |

#### `ProcessPackage_ProcessDef` — （無中文名）　(列數約 47,915)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `ProcessPackageOID` |  | nchar(32) | N | PK |
| `ProcessDefinitionOID` |  | nchar(32) | N | PK |

#### `ProcessDefinitionHeader` — （無中文名）　(列數約 1,618)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `createdTime` |  | datetime | N |  |
| `description` |  | ntext | Y |  |
| `durationUnit` |  | nvarchar(50) | Y |  |
| `limits` |  | real | Y |  |
| `priority` |  | nvarchar(50) | Y |  |
| `timeEstimationOID` |  | nchar(32) | Y |  |
| `validFrom` |  | datetime | Y |  |
| `objectVersion` |  | int | N |  |
| `validTo` |  | datetime | Y |  |
| `limitTemplate` |  | nvarchar(255) | Y |  |

#### `ProcessViewInformation` — （無中文名）　(列數約 1,618)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `startActivityBoundInfoOID` |  | nchar(32) | Y |  |
| `endActivityBoundInfoOID` |  | nchar(32) | Y |  |

#### `ProcessPackageHeader` — （無中文名）　(列數約 1,608)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `costUnit` |  | nvarchar(50) | Y |  |
| `createdTime` |  | datetime | N |  |
| `description` |  | ntext | Y |  |
| `documentation` |  | nvarchar(100) | Y |  |
| `priorityUnit` |  | nvarchar(50) | Y |  |
| `vendor` |  | nvarchar(50) | N |  |
| `objectVersion` |  | int | N |  |
| `xpdlVersion` |  | nvarchar(10) | N |  |
| `bpmnVersion` |  | nvarchar(10) | Y |  |

#### `ProcessPackage` — （無中文名）　(列數約 1,597)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `conformanceClassOID` |  | nchar(32) | Y |  |
| `headerOID` |  | nchar(32) | N |  |
| `id` |  | nvarchar(100) | N |  |
| `processPackageName` |  | nvarchar(100) | Y |  |
| `redefinableHeaderOID` |  | nchar(32) | N |  |
| `objectVersion` |  | int | N |  |
| `scriptDefinitionOID` |  | nchar(32) | Y |  |
| `containerOID` |  | char(32) | N |  |
| `firstActIsReqstPerform` |  | int | N |  |
| `packageInvokeAuthorityOID` |  | char(32) | Y |  |
| `mainProcessDefinitionId` |  | nvarchar(100) | Y |  |
| `userDefineMode` |  | nvarchar(50) | N |  |
| `userInputSubject` |  | int | N |  |
| `subjectTemplet` |  | nvarchar(1000) | Y |  |
| `bundleContainer` |  | ntext | Y |  |
| `formInstanceType` |  | int | N |  |
| `flowType` |  | nvarchar(30) | Y |  |
| `processModel` |  | nchar(4) | Y |  |

#### `ProcessDefinitionSys` — （無中文名）　(列數約 639)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `integratedSys` |  | nvarchar(50) | Y |  |
| `refId01` |  | nvarchar(50) | Y |  |
| `refId02` |  | nvarchar(50) | Y |  |

#### `ProcessMappingKey` — （無中文名）　(列數約 593)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `createdTime` |  | datetime | N |  |
| `processSerialNumber` |  | nvarchar(100) | Y |  |
| `wfRuntimeValueOID` |  | nchar(32) | Y |  |
| `systemKey` |  | nvarchar(255) | N |  |
| `targetSystem` |  | nvarchar(50) | N |  |
| `targetSystemVersion` |  | nvarchar(20) | Y |  |
| `status` |  | nvarchar(2) | Y |  |
| `programId` |  | nvarchar(255) | Y |  |
| `sourceFormNum` |  | nvarchar(255) | Y |  |
| `companyId` |  | nvarchar(50) | Y |  |
| `attachInfo` |  | ntext | Y |  |

#### `ProgramAccessRight` — （無中文名）　(列數約 211)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `ownerOID` |  | nchar(32) | N |  |
| `accessType` |  | int | N |  |
| `containerOID` |  | nchar(32) | N |  |
| `isIncludeSubUnit` |  | int | N |  |
| `ownerType` |  | nvarchar(50) | N |  |
| `updateTime` |  | datetime | N |  |
| `updaterOID` |  | nchar(32) | N |  |

#### `ProgramDefinition` — （無中文名）　(列數約 199)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `id` |  | nvarchar(50) | N |  |
| `name` |  | nvarchar(100) | N |  |
| `linkUrl` |  | nvarchar(255) | N |  |
| `isDefault` |  | int | N |  |
| `bundleContainer` |  | ntext | Y |  |
| `containerOID` |  | nchar(32) | N |  |
| `urlType` |  | int | Y |  |
| `authorizable` |  | int | N |  |

#### `ProcessPackageCmItem` — （無中文名）　(列數約 103)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `checkInTime` |  | datetime | Y |  |
| `checkoutTime` |  | datetime | Y |  |
| `checkoutUserOID` |  | nchar(32) | Y |  |
| `id` |  | nvarchar(100) | N |  |
| `lastVersion` |  | int | N |  |
| `categoryOID` |  | nchar(32) | Y |  |

#### `ProcessPackageCategory` — （無中文名）　(列數約 13)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `packageCategoryName` |  | nvarchar(100) | N |  |
| `id` |  | nvarchar(100) | Y |  |
| `categoryModel` |  | nchar(4) | Y |  |

#### `ProcessUserFocus` — （無中文名）　(列數約 5)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `processInstanceOID` |  | nchar(32) | N |  |
| `updateTime` |  | datetime | N |  |
| `updaterOID` |  | nchar(32) | N |  |

#### `ProcessCtx_GblRelevantData` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `ProcessContextOID` |  | nchar(32) | N | PK |
| `GlobalRelevantDataOID` |  | nchar(32) | N | PK |

#### `ProcessDefTemplate` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `accessLevel` |  | nvarchar(50) | N |  |
| `id` |  | nvarchar(100) | N |  |
| `headerOID` |  | nchar(32) | N |  |
| `processDefinitionName` |  | nvarchar(100) | Y |  |
| `objectVersion` |  | int | N |  |
| `redefinableHeaderOID` |  | nchar(32) | Y |  |
| `containerOID` |  | nchar(32) | N |  |
| `applyDefaultNoticeContent` |  | int | N |  |
| `relationManDefId` |  | nvarchar(100) | Y |  |
| `lastActivityIdNum` |  | int | N |  |
| `lastActivitySetIdNum` |  | int | N |  |
| `lastTransitionIdNum` |  | int | N |  |
| `lastParticipantIdNum` |  | int | N |  |
| `lastFormalParameterIdNum` |  | int | N |  |
| `allowCanceled` |  | int | N |  |
| `notificationIntervalTimeUnit` |  | nvarchar(50) | N |  |
| `multiNotificationIntervalTime` |  | int | N |  |
| `multiNotification` |  | int | N |  |
| `actionAfterAbortedOID` |  | nchar(32) | Y |  |
| `actionAfterTerminatedOID` |  | nchar(32) | Y |  |
| `actionAfterCompletedOID` |  | nchar(32) | Y |  |
| `processViewInformationOID` |  | nchar(32) | Y |  |

#### `ProcessDefTemplateCmItem` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `checkInTime` |  | datetime | Y |  |
| `checkoutTime` |  | datetime | Y |  |
| `checkoutUserOID` |  | nchar(32) | Y |  |
| `id` |  | nvarchar(100) | N |  |
| `lastVersion` |  | int | N |  |

#### `ProcessModuleAccessRight` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nvarchar(32) | N |  |
| `objectVersion` |  | int | N |  |
| `ownerOID` |  | nvarchar(32) | N |  |
| `accessType` |  | int | N |  |
| `containerOID` |  | nvarchar(32) | N |  |
| `isIncludeSubUnit` |  | int | N |  |
| `ownerType` |  | nvarchar(50) | N |  |
| `updateTime` |  | datetime | N |  |
| `updaterOID` |  | nchar(32) | N |  |

#### `ProcessModuleContainer` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nvarchar(32) | N |  |
| `objectVersion` |  | int | N |  |
| `moduleOID` |  | nvarchar(32) | N |  |
| `categoryOID` |  | nvarchar(32) | N |  |

#### `ProcessModuleDefinition` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nvarchar(32) | N |  |
| `objectVersion` |  | int | N |  |
| `id` |  | nvarchar(50) | N |  |
| `name` |  | nvarchar(100) | N |  |
| `bundleContainer` |  | ntext | N |  |
| `updateTime` |  | datetime | N |  |
| `updaterOID` |  | nchar(32) | N |  |

#### `ProcessSubstituteDefinition` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `invokeOrganizationUnitOID` |  | nchar(32) | Y |  |
| `ownerOID` |  | nchar(32) | Y |  |
| `processPackageId` |  | nvarchar(100) | N |  |
| `objectVersion` |  | int | N |  |
| `substituteOID` |  | nchar(32) | N |  |
| `processPackageName` |  | nvarchar(100) | Y |  |
| `alwaysApply` |  | int | N |  |
| `startSubstituteTime` |  | datetime | Y |  |
| `endSubstituteTime` |  | datetime | Y |  |
| `substitutiveOrder` |  | int | N |  |

#### `ProcessTemplate` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `templateId` |  | nvarchar(100) | N |  |
| `templateName` |  | nvarchar(100) | N |  |
| `description` |  | ntext | Y |  |
| `xmlEntityOID` |  | nvarchar(100) | N |  |

#### `ProcessTemplateEntity` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `xmlContainer` |  | ntext | Y |  |

### 前綴 `Loc` — —（3 表）


#### `LocalRelevantData` — （無中文名）　(列數約 385,201)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `containerOID` |  | nchar(32) | N |  |
| `id` |  | nvarchar(100) | N |  |
| `objectVersion` |  | int | N |  |
| `valueOID` |  | nchar(32) | Y |  |
| `dataTypeOID` |  | nchar(32) | Y |  |

#### `LocalNoticeWorkItem` — （無中文名）　(列數約 61,722)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `workAssignmentOID` |  | nchar(32) | N |  |
| `workItemOID` |  | nchar(32) | N |  |
| `userOID` |  | nchar(32) | N |  |
| `bundleContainer` |  | ntext | Y |  |
| `subject` |  | ntext | Y |  |
| `processInstanceName` |  | nvarchar(100) | N |  |
| `createdTime` |  | datetime | N |  |
| `lvlValue` |  | int | N |  |
| `isView` |  | nvarchar(1) | Y |  |

#### `LocalToDoWorkItem` — （無中文名）　(列數約 899)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `workAssignmentOID` |  | nchar(32) | N |  |
| `workItemOID` |  | nchar(32) | Y |  |
| `userOID` |  | nchar(32) | N |  |
| `bundleContainer` |  | ntext | Y |  |
| `subject` |  | ntext | Y |  |
| `processInstanceName` |  | nvarchar(100) | N |  |
| `createdTime` |  | datetime | N |  |
| `lvlValue` |  | int | N |  |

### 前綴 `Not` — —（1 表）


#### `NotificationContent` — （無中文名）　(列數約 417,405)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `localeString` |  | nvarchar(100) | N |  |
| `contentType` |  | int | N |  |
| `subjectValue` |  | nvarchar(255) | Y |  |
| `messageValue` |  | ntext | Y |  |
| `senderText` |  | nvarchar(255) | Y |  |
| `containerOID` |  | nchar(32) | Y |  |
| `receiver` |  | nvarchar(255) | Y |  |
| `mailFormatType` |  | int | N |  |

### 前綴 `For` — 表單(Form)（19 表）


#### `FormInstance` — （無中文名）　(列數約 151,566)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `creatorOID` |  | nchar(32) | N |  |
| `definitionOID` |  | nchar(32) | N |  |
| `fieldValues` |  | ntext | N |  |
| `signedFieldValues` |  | ntext | Y |  |
| `objectVersion` |  | int | N |  |
| `serialNumber` |  | nvarchar(100) | Y |  |
| `maskFieldValues` |  | ntext | Y |  |

#### `FormOperationDefinition` — （無中文名）　(列數約 48,948)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `operationType` |  | int | N |  |
| `objectVersion` |  | int | N |  |

#### `FormFieldAccessDefinition` — （無中文名）　(列數約 45,500)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `formFieldAccessControl` |  | ntext | Y |  |
| `formCloudAccessControl` |  | ntext | Y |  |
| `formValidateAccessControl` |  | ntext | Y |  |
| `formFieldMobileAccessControl` |  | ntext | Y |  |
| `formValidateMobileAccess` |  | ntext | Y |  |

#### `FormalParameter` — （無中文名）　(列數約 4,434)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `containerOID` |  | nchar(32) | Y |  |
| `description` |  | ntext | Y |  |
| `id` |  | nvarchar(100) | N |  |
| `parameterIndex` |  | int | N |  |
| `objectVersion` |  | int | N |  |
| `parameterMode` |  | nvarchar(50) | N |  |
| `formalParameterName` |  | nvarchar(100) | Y |  |
| `dataTypeOID` |  | nchar(32) | N |  |

#### `FormDefinition` — （無中文名）　(列數約 1,906)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `authorName` |  | nvarchar(50) | N |  |
| `createdTime` |  | datetime | N |  |
| `description` |  | ntext | Y |  |
| `id` |  | nvarchar(100) | N |  |
| `formDefinitionName` |  | nvarchar(100) | N |  |
| `publicationStatus` |  | nvarchar(50) | N |  |
| `version` |  | int | N |  |
| `validFrom` |  | datetime | N |  |
| `validTo` |  | datetime | Y |  |
| `containerOID` |  | nchar(32) | Y |  |
| `script` |  | ntext | Y |  |
| `defSerialize` |  | ntext | Y |  |
| `multiZhMap` |  | ntext | Y |  |
| `mobileScript` |  | ntext | Y |  |
| `rwdLayout` |  | ntext | Y |  |
| `scriptInfo` |  | ntext | Y |  |
| `mobileScriptInfo` |  | ntext | Y |  |

#### `FormType` — （無中文名）　(列數約 1,896)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `formDefinitionId` |  | nvarchar(100) | Y |  |

#### `FormRepository` — （無中文名）　(列數約 255)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | Y |  |
| `createdTime` |  | datetime | Y |  |
| `creatorOID` |  | nchar(32) | Y |  |
| `updatedTime` |  | datetime | Y |  |
| `updaterOID` |  | nchar(32) | Y |  |
| `id` |  | nvarchar(100) | Y |  |
| `name` |  | nvarchar(100) | Y |  |
| `nameKey` |  | nvarchar(100) | Y |  |
| `formDefSerialize` |  | ntext | Y |  |
| `industryCategoryOID` |  | nchar(32) | Y |  |
| `formTypeCategoryOID` |  | nchar(32) | Y |  |
| `description` |  | nvarchar(2000) | Y |  |
| `descriptionKey` |  | nvarchar(2000) | Y |  |

#### `FormDefinitionCmItem` — （無中文名）　(列數約 153)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `checkInTime` |  | datetime | Y |  |
| `checkoutTime` |  | datetime | Y |  |
| `checkoutUserOID` |  | nchar(32) | Y |  |
| `id` |  | nvarchar(100) | N |  |
| `lastVersion` |  | int | N |  |
| `categoryOID` |  | nchar(32) | Y |  |

#### `FormScriptTemplate` — （無中文名）　(列數約 69)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `id` |  | nvarchar(45) | N |  |
| `name` |  | nvarchar(100) | N |  |
| `bundleContainer` |  | ntext | Y |  |
| `script` |  | ntext | Y |  |
| `containerOID` |  | nchar(32) | N |  |
| `updateTime` |  | datetime | N |  |
| `updaterOID` |  | nchar(32) | N |  |
| `type` |  | int | Y |  |

#### `FormSqlClause` — （無中文名）　(列數約 29)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `dbCfgId` |  | nvarchar(100) | N |  |
| `id` |  | nvarchar(100) | N |  |
| `sqlClause` |  | nvarchar(4000) | Y |  |
| `name` |  | nvarchar(256) | N |  |
| `description` |  | nvarchar(1000) | Y |  |
| `lastModifiedTime` |  | datetime | Y |  |
| `modifiedAuthorOID` |  | nvarchar(32) | Y |  |

#### `FormInstance_BAK1212` — （無中文名）　(列數約 26)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | char(32) | N | PK |
| `creatorOID` |  | char(32) | N |  |
| `definitionOID` |  | char(32) | N |  |
| `fieldValues` |  | ntext | N |  |
| `signedFieldValues` |  | ntext | Y |  |
| `objectVersion` |  | int | N |  |
| `serialNumber` |  | nvarchar(50) | Y |  |
| `maskFieldValues` |  | ntext | Y |  |

#### `FormTypeCategory` — （無中文名）　(列數約 25)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | Y |  |
| `createdTime` |  | datetime | Y |  |
| `creatorOID` |  | nchar(32) | Y |  |
| `updatedTime` |  | datetime | Y |  |
| `updaterOID` |  | nchar(32) | Y |  |
| `industryCategoryOID` |  | nchar(32) | Y |  |
| `name` |  | nvarchar(100) | Y |  |
| `nameKey` |  | nvarchar(100) | Y |  |

#### `FormCategory` — （無中文名）　(列數約 13)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `formCategoryName` |  | nvarchar(100) | N |  |
| `objectVersion` |  | int | N |  |

#### `FormScriptCategory` — （無中文名）　(列數約 6)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `id` |  | nvarchar(50) | N |  |
| `name` |  | nvarchar(100) | N |  |
| `bundleContainer` |  | ntext | Y |  |
| `updateTime` |  | datetime | N |  |
| `updaterOID` |  | nchar(32) | N |  |

#### `FormCategoryAccessRight` — （無中文名）　(列數約 2)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `rightType` |  | int | N |  |
| `categoryOID` |  | nchar(32) | N |  |
| `ownerId` |  | nvarchar(100) | N |  |
| `organizationId` |  | nvarchar(100) | N |  |
| `includeSubCate` |  | int | N |  |

#### `FormColumnMask` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | Y |  |
| `formId` |  | nvarchar(100) | N |  |
| `gridId` |  | nvarchar(100) | Y |  |
| `columnId` |  | nvarchar(100) | N |  |
| `perDataProId` |  | nvarchar(100) | N |  |

#### `FormDataObject` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `creatorOID` |  | nchar(32) | N |  |
| `definitionOID` |  | nchar(32) | N |  |
| `valueOID` |  | nchar(32) | N |  |
| `attachmentXML` |  | ntext | Y |  |
| `serialNumber` |  | nvarchar(100) | Y |  |

#### `FormDesignAssistant` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | Y |  |
| `createdTime` |  | datetime | Y |  |
| `creatorOID` |  | nvarchar(32) | Y |  |
| `updatedTime` |  | datetime | Y |  |
| `updaterOID` |  | nvarchar(32) | Y |  |
| `sourceFileOID` |  | nvarchar(32) | Y |  |
| `sourceFileName` |  | nvarchar(255) | Y |  |
| `uploaderId` |  | nvarchar(100) | Y |  |
| `uploaderName` |  | nvarchar(100) | Y |  |
| `processingStatus` |  | int | Y |  |
| `parsingCompletedTime` |  | datetime | Y |  |
| `parsingResultJson` |  | ntext | Y |  |
| `formId` |  | nvarchar(100) | Y |  |
| `formName` |  | nvarchar(100) | Y |  |
| `formCategory` |  | nchar(32) | Y |  |
| `formCategoryName` |  | nvarchar(100) | Y |  |
| `fieldTemplate` |  | nvarchar(15) | Y |  |
| `formGeneratedTime` |  | datetime | Y |  |
| `totalToken` |  | int | Y |  |
| `decreaseCount` |  | int | Y |  |
| `usedCount` |  | int | Y |  |
| `compensatedFromOID` |  | nchar(32) | Y |  |
| `compensatedByOID` |  | nchar(32) | Y |  |

#### `FormFieldAccessDefault` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `ProcessDefinitionOID` |  | nchar(32) | N |  |
| `ActivityDefinitionOID` |  | nchar(32) | Y |  |

### 前綴 `Str` — —（3 表）


#### `StringWorkflowRuntimeValue` — （無中文名）　(列數約 233,317)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `stringValue` |  | ntext | Y |  |

#### `StrategyAssignDefinition` — （無中文名）　(列數約 2,898)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `isMeanAssignment` |  | int | N |  |
| `strategyAssignInstanceOID` |  | nchar(32) | N |  |

#### `StrategyAssignInstance` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `total` |  | int | N |  |

### 前綴 `IAp` — —（1 表）


#### `IAppDefContainer_AppDef` — （無中文名）　(列數約 210,297)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `IAppDefContainerOID` |  | nchar(32) | N | PK |
| `ApplicationDefinitionOID` |  | nchar(32) | N | PK |

### 前綴 `dfs` — 自訂(df)（11 表）


#### `dfsale_detail` — （無中文名）　(列數約 110,487)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `dfsalegd_price` |  | float | Y |  |
| `dfsalegd_note` |  | nvarchar(255) | Y |  |
| `dfsalegd_unitname` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `dfsalegd_sum` |  | float | Y |  |
| `dfsalegd_stuffname` |  | nvarchar(255) | Y |  |
| `dfsalegd_weight` |  | float | Y |  |
| `dfsalegd_unitcode` |  | nvarchar(255) | Y |  |
| `dfsalegd_no` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `dfsalegd_stuffcode` |  | nvarchar(255) | Y |  |

#### `dfsale` — （無中文名）　(列數約 55,038)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `dfsale_stuffname` |  | nvarchar(255) | Y |  |
| `Textbox48` |  | nvarchar(255) | Y |  |
| `dfsale_deptname` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `dfsale_chktype` |  | nvarchar(255) | Y |  |
| `dfsale_weight` |  | float | Y |  |
| `dfsale_tax` |  | float | Y |  |
| `dfsale_desc` |  | nvarchar(2000) | Y |  |
| `dfsale_appdate` |  | nvarchar(255) | Y |  |
| `dfsale_date` |  | datetime | Y |  |
| `dfsale_custcode` |  | nvarchar(255) | Y |  |
| `dfsale_deptcode` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `dfsale_chkdesc` |  | nvarchar(2000) | Y |  |
| `dfsale_sum` |  | float | Y |  |
| `dfsale_total` |  | float | Y |  |
| `dfsale_usercode` |  | nvarchar(255) | Y |  |
| `dfsale_money` |  | float | Y |  |
| `dfsale_unitcode` |  | nvarchar(255) | Y |  |
| `dfsale_convey` |  | nvarchar(255) | Y |  |
| `dfsale_title` |  | nvarchar(255) | Y |  |
| `dfsale_note` |  | nvarchar(255) | Y |  |
| `dfsale_sitecode` |  | nvarchar(255) | Y |  |
| `dfsale_price` |  | float | Y |  |
| `dfsale_chktax` |  | nvarchar(255) | Y |  |
| `dfsale_stuffcode` |  | nvarchar(255) | Y |  |
| `dfsale_custname` |  | nvarchar(255) | Y |  |
| `dfsale_unitname` |  | nvarchar(255) | Y |  |
| `dfsale_monetary` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `dfsale_hdn_username` |  | nvarchar(255) | Y |  |
| `dfsale_hdn_unitcode` |  | nvarchar(255) | Y |  |
| `dfsale_hdn_fsite` |  | nvarchar(255) | Y |  |
| `dfsale_hdn_deptcode` |  | nvarchar(255) | Y |  |
| `dfsale_hdn_stuffcode` |  | nvarchar(255) | Y |  |
| `dfsale_hdn_monetaryname` |  | nvarchar(255) | Y |  |
| `dfsale_hdn_sitename` |  | nvarchar(255) | Y |  |
| `dfsale_hdn_boss` |  | nvarchar(255) | Y |  |
| `dfsale_hdn_custcode` |  | nvarchar(255) | Y |  |
| `dfsale_hdn_deptOID` |  | nvarchar(255) | Y |  |
| `dfsale_hdn_edesc` |  | nvarchar(2000) | Y |  |
| `hdndfsale_chktypename` |  | nvarchar(255) | Y |  |
| `dfsale_no` |  | nvarchar(255) | Y |  |
| `hdndfsale_conveyname` |  | nvarchar(255) | Y |  |

#### `dfsale_b_detail` — （無中文名）　(列數約 8,006)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `dfsalegd_price` |  | nvarchar(255) | Y |  |
| `dfsalegd_note` |  | nvarchar(255) | Y |  |
| `dfsalegd_unitname` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `dfsalegd_sum` |  | nvarchar(255) | Y |  |
| `dfsalegd_stuffname` |  | nvarchar(255) | Y |  |
| `dfsalegd_weight` |  | nvarchar(255) | Y |  |
| `dfsalegd_no` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `dfsalegd_stuffcode` |  | nvarchar(255) | Y |  |

#### `dfsuggest` — （無中文名）　(列數約 6,077)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `dfsug_secert` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `dfsug_advise` |  | nvarchar(3000) | Y |  |
| `dfsug_hdn_deptcode` |  | nvarchar(255) | Y |  |
| `dfsug_title` |  | nvarchar(500) | Y |  |
| `dfsug_user` |  | nvarchar(255) | Y |  |
| `dfsug_hdn_username` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `dfsug_sdate` |  | datetime | Y |  |
| `dfsug_no` |  | nvarchar(255) | Y |  |
| `dfsug_desc` |  | nvarchar(3000) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `dfsug_kind` |  | nvarchar(255) | Y |  |
| `dfsug_deptname` |  | nvarchar(255) | Y |  |
| `dfsug_hdn_edesc` |  | nvarchar(255) | Y |  |
| `hdndfsug_secertname` |  | nvarchar(255) | Y |  |
| `hdndfsug_kindname` |  | nvarchar(255) | Y |  |

#### `dfsale_b` — （無中文名）　(列數約 5,508)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `dfsale_stuffname` |  | nvarchar(255) | Y |  |
| `Textbox48` |  | nvarchar(255) | Y |  |
| `dfsale_deptname` |  | nvarchar(255) | Y |  |
| `dfsale_hdn_fsite` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `dfsale_chktype` |  | nvarchar(255) | Y |  |
| `dfsale_weight` |  | float | Y |  |
| `dfsale_hdn_deptcode` |  | nvarchar(255) | Y |  |
| `dfsale_tax` |  | float | Y |  |
| `dfsale_hdn_stuffcode` |  | nvarchar(255) | Y |  |
| `dfsale_desc` |  | nvarchar(255) | Y |  |
| `dfsale_appdate` |  | nvarchar(255) | Y |  |
| `dfsale_hdn_username` |  | nvarchar(255) | Y |  |
| `dfsale_hdn_monetaryname` |  | nvarchar(255) | Y |  |
| `dfsale_date` |  | datetime | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `dfsale_chkdesc` |  | nvarchar(255) | Y |  |
| `dfsale_sum` |  | float | Y |  |
| `dfsale_total` |  | float | Y |  |
| `dfsale_hdn_sitename` |  | nvarchar(255) | Y |  |
| `dfsale_hdn_boss` |  | nvarchar(255) | Y |  |
| `dfsale_kind` |  | nvarchar(255) | Y |  |
| `dfsale_usercode` |  | nvarchar(255) | Y |  |
| `dfsale_money` |  | float | Y |  |
| `dfsale_hdn_edesc` |  | nvarchar(255) | Y |  |
| `dfsale_hdn_custcode` |  | nvarchar(255) | Y |  |
| `dfsale_convey` |  | nvarchar(255) | Y |  |
| `dfsale_title` |  | nvarchar(255) | Y |  |
| `dfsale_note` |  | nvarchar(255) | Y |  |
| `dfsale_sitecode` |  | nvarchar(255) | Y |  |
| `dfsale_price` |  | float | Y |  |
| `dfsale_chktax` |  | nvarchar(255) | Y |  |
| `dfsale_custname` |  | nvarchar(255) | Y |  |
| `dfsale_unitname` |  | nvarchar(255) | Y |  |
| `dfsale_hdn_deptOID` |  | nvarchar(255) | Y |  |
| `dfsale_monetary` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `hdndfsale_chktypename` |  | nvarchar(255) | Y |  |
| `hdndfsale_kindname` |  | nvarchar(255) | Y |  |
| `dfsale_no` |  | nvarchar(255) | Y |  |
| `hdndfsale_conveyname` |  | nvarchar(255) | Y |  |

#### `dfstuffmatch` — （無中文名）　(列數約 125)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `dfmatch_stuffdesc` |  | nvarchar(255) | Y |  |
| `dfmatch_stuffcode` |  | nvarchar(255) | Y |  |
| `dfmatch_address` |  | nvarchar(255) | Y |  |
| `dfmatch_quottype` |  | nvarchar(255) | Y |  |
| `dfmatch_stuffbtype` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `hdn_dfmatch_stuffbtype` |  | nvarchar(255) | Y |  |
| `dfmatch_eprice` |  | float | Y |  |
| `dfmatch_area` |  | nvarchar(255) | Y |  |
| `hdn_dfmatch_dealdate` |  | nvarchar(255) | Y |  |
| `dfmatch_username` |  | nvarchar(255) | Y |  |
| `hdn_dfmatch_deliver` |  | nvarchar(255) | Y |  |
| `dfmatch_style` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `dfmatch_title` |  | nvarchar(255) | Y |  |
| `dfmatch_termdate` |  | datetime | Y |  |
| `hdn_dfmatch_termdate` |  | nvarchar(255) | Y |  |
| `dfmatch_deliver` |  | nvarchar(255) | Y |  |
| `hdn_dfmatch_nation` |  | nvarchar(255) | Y |  |
| `hdn_dfmatch_termtype` |  | nvarchar(255) | Y |  |
| `dfmatch_money` |  | nvarchar(255) | Y |  |
| `hdn_dfmatch_style` |  | nvarchar(255) | Y |  |
| `dfmatch_source` |  | nvarchar(255) | Y |  |
| `dfmatch_code` |  | nvarchar(255) | Y |  |
| `dfmatch_eweight` |  | float | Y |  |
| `hdn_dfmatch_stuffctype` |  | nvarchar(255) | Y |  |
| `dfmatch_stuffctype` |  | nvarchar(255) | Y |  |
| `dfmatch_termtype` |  | nvarchar(255) | Y |  |
| `dfmatch_email` |  | nvarchar(255) | Y |  |
| `dfmatch_sprice` |  | float | Y |  |
| `dfmatch_dealdate` |  | datetime | Y |  |
| `hdn_dfmatch_money` |  | nvarchar(255) | Y |  |
| `dfmatch_type` |  | nvarchar(255) | Y |  |
| `dfmatch_sweight` |  | float | Y |  |
| `dfmatch_nation` |  | nvarchar(255) | Y |  |
| `dfmatch_stuffname` |  | nvarchar(255) | Y |  |
| `dfmatch_tel` |  | nvarchar(255) | Y |  |
| `hdn_dfmatch_type` |  | nvarchar(255) | Y |  |
| `dfmatch_custname` |  | nvarchar(255) | Y |  |
| `dfmatch_appdate` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `hdn_dfmatch_area` |  | nvarchar(255) | Y |  |
| `dfmatch_custcode` |  | nvarchar(255) | Y |  |
| `hdn_weblang` |  | nvarchar(255) | Y |  |
| `Attachment` |  | nvarchar(255) | Y |  |

#### `dfseal_detail` — （無中文名）　(列數約 24)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `dfseal_hdn_gdusemodename` |  | nvarchar(255) | Y |  |
| `dfseal_gddocname` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `dfseal_gdno` |  | nvarchar(255) | Y |  |
| `dfseal_gdcount` |  | nvarchar(255) | Y |  |
| `dfseal_gdusemode` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `dfseal_gdusedesc` |  | nvarchar(255) | Y |  |

#### `dfseal` — （無中文名）　(列數約 15)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `dfseal_lendplace` |  | nvarchar(255) | Y |  |
| `dfseal_hdn_fdept` |  | nvarchar(255) | Y |  |
| `dfseal_hdn_boss` |  | nvarchar(255) | Y |  |
| `dfseal_hdn_deptOID` |  | nvarchar(255) | Y |  |
| `dfseal_usemode` |  | nvarchar(255) | Y |  |
| `dfseal_appdate` |  | datetime | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `dfseal_assign` |  | nvarchar(255) | Y |  |
| `dfseal_hdn_deptcode` |  | nvarchar(255) | Y |  |
| `dfseal_no` |  | varchar(255) | Y |  |
| `dfseal_pregdate` |  | datetime | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `dfseal_deptname` |  | nvarchar(255) | Y |  |
| `dfseal_hdn_edesc` |  | nvarchar(1000) | Y |  |
| `dfseal_usercode` |  | nvarchar(255) | Y |  |
| `dfseal_typedesc` |  | nvarchar(500) | Y |  |
| `dfseal_count` |  | nvarchar(255) | Y |  |
| `dfseal_signet` |  | nvarchar(255) | Y |  |
| `dfseal_docname` |  | nvarchar(255) | Y |  |
| `dfseal_hdn_username` |  | nvarchar(255) | Y |  |
| `dfseal_hdn_usemodename` |  | nvarchar(255) | Y |  |
| `dfseal_assigndesc` |  | nvarchar(500) | Y |  |
| `dfseal_realgdate` |  | datetime | Y |  |
| `dfseal_lenddate` |  | datetime | Y |  |
| `dfseal_usedesc` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `dfseal_type` |  | nvarchar(255) | Y |  |
| `dfseal_no_type` |  | varchar(50) | Y |  |
| `dfseal_no_serial` |  | varchar(20) | Y |  |
| `dfseal_hdn_typename` |  | nvarchar(255) | Y |  |
| `dfseal_sugtitle` |  | nvarchar(500) | Y |  |
| `dfseal_sugthing` |  | nvarchar(3000) | Y |  |

#### `dfstuff` — （無中文名）　(列數約 9)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `dfstuff_unitcode` |  | nvarchar(255) | Y |  |
| `dfstuff_dtype` |  | nvarchar(255) | Y |  |
| `dfstuff_name` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `dfstuff_special` |  | nvarchar(255) | Y |  |
| `dfstuff_deptname` |  | nvarchar(255) | Y |  |
| `dfstuff_style` |  | nvarchar(255) | Y |  |
| `dfstuff_appdate` |  | nvarchar(255) | Y |  |
| `dfstuff_usercode` |  | nvarchar(255) | Y |  |
| `dfstuff_hdn_username` |  | nvarchar(255) | Y |  |
| `dfstuff_btype` |  | nvarchar(255) | Y |  |
| `dfstuff_method` |  | nvarchar(255) | Y |  |
| `dfstuff_meno` |  | nvarchar(255) | Y |  |
| `dfstuff_desc` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `dfstuff_short` |  | nvarchar(255) | Y |  |
| `dfstuff_ctype` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `dfstuff_deptcode` |  | nvarchar(255) | Y |  |

#### `dfsuggest_clone` — （無中文名）　(列數約 9)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `dfsug_hdn_edesc` |  | nvarchar(255) | Y |  |
| `dfsug_sdate` |  | datetime | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `dfsug_advise` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `dfsug_desc` |  | nvarchar(255) | Y |  |
| `dfsug_hdn_username` |  | nvarchar(255) | Y |  |
| `dfsug_title` |  | nvarchar(255) | Y |  |
| `dfsug_user` |  | nvarchar(255) | Y |  |
| `dfsug_no` |  | nvarchar(255) | Y |  |
| `dfsug_kind` |  | nvarchar(255) | Y |  |
| `hdndfsug_secertname` |  | nvarchar(255) | Y |  |
| `dfsug_deptname` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `hdndfsug_kindname` |  | nvarchar(255) | Y |  |
| `dfsug_secert` |  | nvarchar(255) | Y |  |
| `dfsug_hdn_deptcode` |  | nvarchar(255) | Y |  |

#### `dfstuffmatch_attach` — （無中文名）　(列數約 2)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `dfmatchathgd_orgfile` |  | nvarchar(255) | Y |  |
| `dfmatchathgd_code` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `dfmatchathgd_name` |  | nvarchar(255) | Y |  |

### 前綴 `Lic` — —（2 表）


#### `LicenseStatRcd` — （無中文名）　(列數約 148,716)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | Y |  |
| `encodedData` |  | ntext | Y |  |

#### `LicenseReg` — （無中文名）　(列數約 4)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | Y |  |
| `licenseInfo` |  | ntext | Y |  |

### 前綴 `Rel` — —（3 表）


#### `RelevantDataDefinition` — （無中文名）　(列數約 133,235)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `id` |  | nvarchar(100) | N |  |
| `relevantDataDefinitionName` |  | nvarchar(100) | Y |  |
| `containerOID` |  | nchar(32) | Y |  |
| `description` |  | ntext | Y |  |
| `initialValue` |  | nvarchar(1000) | Y |  |
| `isArray` |  | nvarchar(10) | N |  |
| `objectVersion` |  | int | N |  |
| `length` |  | int | Y |  |
| `dataTypeOID` |  | nchar(32) | N |  |

#### `RelatedUnit` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `orgUnitOID` |  | nchar(32) | N |  |
| `documentOID` |  | nchar(32) | N |  |
| `unitType` |  | nvarchar(50) | N |  |

#### `Relationship` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `relationshipName` |  | nvarchar(100) | N |  |
| `ownerOID` |  | nchar(32) | Y |  |
| `relationalManOID` |  | nchar(32) | N |  |
| `showIndex` |  | int | N |  |

### 前綴 `App` — —（2 表）


#### `AppFormActivityRecord` — （無中文名）　(列數約 116,542)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `processSerialNumber` |  | nvarchar(100) | Y |  |
| `identifier` |  | nchar(32) | Y |  |
| `userID` |  | nchar(32) | N |  |
| `actionCode` |  | char(2) | N |  |
| `actionModifiedTime` |  | datetime | N |  |
| `actionFinished` |  | char(1) | N |  |
| `dataCreatedTime` |  | datetime | N |  |
| `userDataXML` |  | ntext | N |  |

#### `AppFormAttachment` — （無中文名）　(列數約 205)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `formInstanceOID` |  | nvarchar(32) | N |  |
| `attachFile` |  | nvarchar(2) | Y |  |
| `essNo` |  | nvarchar(100) | Y |  |

### 前綴 `Bou` — —（1 表）


#### `BoundViewInformation` — （無中文名）　(列數約 105,641)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `xPosition` |  | int | N |  |
| `yPosition` |  | int | N |  |
| `height` |  | int | Y |  |
| `width` |  | int | Y |  |

### 前綴 `Too` — —（1 表）


#### `Tool` — （無中文名）　(列數約 95,031)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `applicationDefinitionId` |  | nvarchar(100) | N |  |
| `containerOID` |  | char(32) | Y |  |
| `toolType` |  | nvarchar(50) | N |  |
| `description` |  | ntext | Y |  |
| `toolIndex` |  | int | N |  |
| `applicationModeOID` |  | nchar(32) | Y |  |
| `objectVersion` |  | int | N |  |
| `id` |  | nvarchar(100) | N |  |
| `toolName` |  | nvarchar(100) | Y |  |

### 前綴 `Blo` — —（2 表）


#### `BlockActivityInstance` — （無中文名）　(列數約 90,771)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `containerOID` |  | nchar(32) | N |  |
| `contextOID` |  | nchar(32) | N |  |
| `currentState` |  | int | N |  |
| `terminateReason` |  | int | Y |  |
| `definitionId` |  | nvarchar(100) | N |  |
| `comeBackActivityInstOID` |  | nchar(32) | Y |  |
| `defaultAssignmentType` |  | int | N |  |
| `objectVersion` |  | int | N |  |
| `createdTime` |  | datetime | N |  |
| `indexActId` |  | nvarchar(100) | Y |  |
| `container1OID` |  | nchar(32) | Y |  |
| `container2OID` |  | nchar(32) | Y |  |
| `redoRefActivityInstOID` |  | nchar(32) | Y |  |

#### `BlockActivity` — （無中文名）　(列數約 2,034)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | char(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `activitySetDefinitionId` |  | nvarchar(100) | N |  |

### 前綴 `OJB` — —（10 表）


#### `OJB_DSET_ENTRIES` — （無中文名）　(列數約 34,049)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `ID` |  | int | N | PK |
| `DLIST_ID` |  | int | N |  |
| `POSITION_` |  | int | Y |  |
| `OID_` |  | image | Y |  |

#### `OJB_DSET` — （無中文名）　(列數約 31,378)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `ID` |  | int | N | PK |
| `SIZE_` |  | int | Y |  |

#### `OJB_DLIST_ENTRIES` — （無中文名）　(列數約 2,827)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `ID` |  | int | N | PK |
| `DLIST_ID` |  | int | N |  |
| `POSITION_` |  | int | Y |  |
| `OID_` |  | image | Y |  |

#### `OJB_DLIST` — （無中文名）　(列數約 2,687)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `ID` |  | int | N | PK |
| `SIZE_` |  | int | Y |  |

#### `OJB_DMAP` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `ID` |  | int | N | PK |
| `SIZE_` |  | int | Y |  |

#### `OJB_DMAP_ENTRIES` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `ID` |  | int | N | PK |
| `DMAP_ID` |  | int | N |  |
| `KEY_OID` |  | image | Y |  |
| `VALUE_OID` |  | image | Y |  |

#### `OJB_HL_SEQ` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `TABLENAME` |  | varchar(175) | N | PK |
| `FIELDNAME` |  | varchar(70) | N | PK |
| `MAX_KEY` |  | int | Y |  |
| `GRAB_SIZE` |  | int | Y |  |
| `VERSION` |  | int | Y |  |

#### `OJB_LOCKENTRY` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID_` |  | varchar(250) | N | PK |
| `TX_ID` |  | varchar(50) | N | PK |
| `TIMESTAMP_` |  | bigint | Y |  |
| `ISOLATIONLEVEL` |  | int | Y |  |
| `LOCKTYPE` |  | int | Y |  |

#### `OJB_NEXTVAL_SEQ` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `SEQ_NAME` |  | varchar(150) | N | PK |
| `MAX_KEY` |  | bigint | Y |  |

#### `OJB_NRM` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `NAME` |  | varchar(250) | N | PK |
| `OID_` |  | image | Y |  |

### 前綴 `DBR` — —（1 表）


#### `DBRsrcBundle` — （無中文名）　(列數約 61,651)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nvarchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `labelKey` |  | nvarchar(255) | N |  |
| `rsrcType` |  | nvarchar(10) | N |  |
| `labelValue` |  | ntext | N |  |
| `updaterOID` |  | nchar(32) | N |  |
| `updateTime` |  | datetime | N |  |

### 前綴 `Imp` — —（1 表）


#### `Implementation` — （無中文名）　(列數約 51,804)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `objectVersion` |  | int | N |  |
| `OID` |  | char(32) | N | PK |

### 前綴 `dfp` — —（3 表）


#### `dfpurchase_detail` — （無中文名）　(列數約 31,207)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `dfpur_gdunit` |  | nvarchar(255) | Y |  |
| `dfpur_gdno` |  | nvarchar(255) | Y |  |
| `dfpur_gditem` |  | nvarchar(255) | Y |  |
| `dfpur_gdsum` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `dfpur_gdprice` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `dfpur_gdcount` |  | nvarchar(255) | Y |  |

#### `dfpurchase` — （無中文名）　(列數約 15,967)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `dfpur_hdn_deptcode` |  | nvarchar(255) | Y |  |
| `dfpur_convey` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `dfpur_appdate` |  | nvarchar(255) | Y |  |
| `dfpur_sum` |  | float | Y |  |
| `dfpur_supplier` |  | nvarchar(300) | Y |  |
| `dfpur_money` |  | float | Y |  |
| `dfpur_type` |  | nvarchar(255) | Y |  |
| `dfpur_price` |  | float | Y |  |
| `dfpur_tax` |  | nvarchar(255) | Y |  |
| `dfpur_deptname` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `dfpur_status` |  | nvarchar(255) | Y |  |
| `dfpur_hdn_statuscode` |  | nvarchar(255) | Y |  |
| `dfpur_hdn_deptOID` |  | nvarchar(255) | Y |  |
| `dfpur_user` |  | nvarchar(255) | Y |  |
| `dfpur_refer` |  | nvarchar(max) | Y |  |
| `dfpur_hdn_username` |  | nvarchar(255) | Y |  |
| `dfpur_reqdate` |  | datetime | Y |  |
| `dfpur_item` |  | nvarchar(max) | Y |  |
| `dfpur_desc` |  | nvarchar(max) | Y |  |
| `dfpur_no` |  | nvarchar(255) | Y |  |
| `dfpur_hdn_boss` |  | nvarchar(255) | Y |  |
| `dfpur_chktax` |  | nvarchar(255) | Y |  |
| `dfpur_other` |  | nvarchar(255) | Y |  |
| `dfpur_unit` |  | nvarchar(255) | Y |  |
| `dfpur_title` |  | nvarchar(255) | Y |  |
| `dfpur_place` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `dfpur_total` |  | nvarchar(255) | Y |  |
| `dfpur_count` |  | float | Y |  |
| `dfpur_hdn_fdept` |  | nvarchar(255) | Y |  |
| `dfpur_hdn_edesc` |  | nvarchar(255) | Y |  |
| `dfpur_appkind` |  | nvarchar(255) | Y |  |
| `hdndfpur_typename` |  | nvarchar(255) | Y |  |
| `hdndfpur_appkindname` |  | nvarchar(255) | Y |  |

#### `dfprint` — （無中文名）　(列數約 1)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `RB1` |  | nvarchar(255) | Y |  |
| `TB1` |  | nvarchar(255) | Y |  |
| `TB3` |  | nvarchar(255) | Y |  |
| `TB2` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `TB5` |  | nvarchar(255) | Y |  |
| `TB4` |  | nvarchar(255) | Y |  |
| `TB7` |  | nvarchar(255) | Y |  |
| `TB6` |  | nvarchar(255) | Y |  |
| `TB9` |  | nvarchar(255) | Y |  |
| `TB8` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `CH10` |  | nvarchar(255) | Y |  |
| `SN` |  | nvarchar(255) | Y |  |
| `DT1` |  | datetime | Y |  |
| `DT3` |  | datetime | Y |  |
| `DT2` |  | datetime | Y |  |
| `HT1` |  | nvarchar(255) | Y |  |
| `TA1` |  | nvarchar(255) | Y |  |
| `HT2` |  | nvarchar(255) | Y |  |
| `TB10` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `CH2` |  | nvarchar(255) | Y |  |
| `CH1` |  | nvarchar(255) | Y |  |
| `CH4` |  | nvarchar(255) | Y |  |
| `CH3` |  | nvarchar(255) | Y |  |
| `CH6` |  | nvarchar(255) | Y |  |
| `CH5` |  | nvarchar(255) | Y |  |
| `CH8` |  | nvarchar(255) | Y |  |
| `CH7` |  | nvarchar(255) | Y |  |
| `CH9` |  | nvarchar(255) | Y |  |

### 前綴 `Cus` — —（4 表）


#### `CustomProcessPackage` — （無中文名）　(列數約 46,303)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `conformanceClassOID` |  | nchar(32) | Y |  |
| `headerOID` |  | nchar(32) | N |  |
| `id` |  | nvarchar(100) | N |  |
| `processPackageName` |  | nvarchar(100) | Y |  |
| `redefinableHeaderOID` |  | nchar(32) | N |  |
| `objectVersion` |  | int | N |  |
| `scriptDefinitionOID` |  | nchar(32) | Y |  |
| `mainProcessDefinitionId` |  | nvarchar(100) | Y |  |
| `userInputSubject` |  | int | N |  |
| `subjectTemplet` |  | nvarchar(1000) | Y |  |
| `formInstanceType` |  | int | N |  |
| `bundleContainer` |  | ntext | Y |  |
| `containerOID` |  | nchar(32) | Y |  |
| `firstActIsReqstPerform` |  | int | Y |  |
| `flowType` |  | nvarchar(30) | Y |  |
| `packageInvokeAuthorityOID` |  | nchar(32) | Y |  |
| `processModel` |  | nchar(4) | Y |  |
| `userDefineMode` |  | nvarchar(50) | Y |  |

#### `CustomAccessRight` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `id` |  | nvarchar(100) | N |  |
| `accessRightName` |  | nvarchar(100) | N |  |
| `description` |  | ntext | Y |  |

#### `CustomDataChooserConf` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `id` |  | nvarchar(100) | N |  |
| `title` |  | nvarchar(300) | N |  |
| `titleRsrc` |  | ntext | Y |  |
| `width` |  | int | N |  |
| `height` |  | int | N |  |
| `prevEvent` |  | nvarchar(100) | Y |  |
| `nextEvent` |  | nvarchar(100) | Y |  |
| `dbCfgId` |  | nvarchar(100) | N |  |
| `sqlClause` |  | ntext | Y |  |
| `queryLabel` |  | ntext | N |  |
| `queryLabelRsrc` |  | ntext | Y |  |
| `queryFiled` |  | ntext | N |  |
| `gridTitle` |  | ntext | N |  |
| `gridTitleRsrc` |  | ntext | Y |  |
| `description` |  | ntext | Y |  |
| `updateTime` |  | datetime | N |  |
| `updaterOID` |  | nchar(32) | N |  |

#### `CustomQuery` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `bundleContainer` |  | ntext | Y |  |
| `createdTime` |  | datetime | N |  |
| `creatorOID` |  | nchar(32) | N |  |
| `dataModelId` |  | nvarchar(100) | Y |  |
| `defaultQueryVersion` |  | int | Y |  |
| `description` |  | nvarchar(1000) | Y |  |
| `fixedCondsString` |  | ntext | Y |  |
| `modelType` |  | int | N |  |
| `modifiedTime` |  | datetime | Y |  |
| `modifiedUserOID` |  | nchar(32) | Y |  |
| `name` |  | nvarchar(255) | N |  |
| `queryColsString` |  | ntext | Y |  |
| `queryId` |  | nvarchar(100) | N |  |
| `queryOrderByColsString` |  | ntext | Y |  |
| `queryResultColsString` |  | ntext | Y |  |

### 前綴 `Dec` — —（11 表）


#### `DecisionLevel` — （無中文名）　(列數約 12,897)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `containerOID` |  | nchar(32) | Y |  |
| `decisionLevelName` |  | nvarchar(100) | N |  |
| `approvalLevelOID` |  | nchar(32) | N |  |
| `showIndex` |  | int | N |  |

#### `DecisionRule` — （無中文名）　(列數約 11,303)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `decisionConditionOID` |  | nchar(32) | N |  |
| `decisionLevelOID` |  | nchar(32) | Y |  |

#### `DecisionCondition` — （無中文名）　(列數約 5,041)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `containerOID` |  | nchar(32) | Y |  |
| `content` |  | ntext | Y |  |
| `showIndex` |  | int | N |  |
| `description` |  | nvarchar(1000) | Y |  |

#### `DecisionRuleList` — （無中文名）　(列數約 1,974)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `decisionRuleListName` |  | nvarchar(100) | N |  |
| `id` |  | nvarchar(100) | N |  |
| `isManagerDecide` |  | int | N |  |
| `referActivityId` |  | nvarchar(100) | Y |  |
| `preActRelationName` |  | nvarchar(100) | Y |  |
| `decisionPatternId` |  | nvarchar(100) | Y |  |
| `activityDefinitionEntityOID` |  | nchar(32) | Y |  |

#### `DecisionConditionSharing` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `containerOID` |  | nchar(32) | N |  |
| `content` |  | ntext | Y |  |
| `showIndex` |  | int | N |  |

#### `DecisionLevelSharing` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `containerOID` |  | nchar(32) | N |  |
| `decisionLevelName` |  | nvarchar(100) | N |  |
| `approvalLevelOID` |  | nchar(32) | N |  |
| `showIndex` |  | int | N |  |

#### `DecisionPatterns` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `id` |  | nvarchar(100) | N |  |
| `name` |  | nvarchar(100) | N |  |
| `description` |  | ntext | Y |  |
| `decisionRuleListOID` |  | nchar(32) | Y |  |

#### `DecisionPatternsMapping` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `processDefinitionId` |  | nvarchar(100) | N |  |
| `activityId` |  | nvarchar(100) | N |  |
| `decisionPatternId` |  | nvarchar(100) | N |  |
| `processDefinitionOID` |  | nchar(32) | Y |  |

#### `DecisionRuleListSharing` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `decisionRuleListName` |  | nvarchar(100) | N |  |
| `id` |  | nvarchar(100) | N |  |
| `isManagerDecide` |  | int | N |  |
| `referActivityId` |  | nvarchar(100) | Y |  |
| `preActRelationName` |  | nvarchar(100) | Y |  |

#### `DecisionRuleSharing` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `decisionConditionOID` |  | nchar(32) | N |  |
| `decisionLevelOID` |  | nchar(32) | N |  |

#### `DeclaredType` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `typeDefinitionId` |  | nvarchar(100) | N |  |

### 前綴 `NoC` — —（2 表）


#### `NoCmDocument` — （無中文名）　(列數約 17,917)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `createdTime` |  | datetime | N |  |
| `extentionName` |  | nvarchar(100) | Y |  |
| `id` |  | nvarchar(100) | N |  |
| `logicalName` |  | nvarchar(255) | Y |  |
| `physicalName` |  | nvarchar(255) | N |  |
| `creatorOID` |  | nchar(32) | N |  |
| `typeOID` |  | nchar(32) | N |  |
| `description` |  | ntext | Y |  |
| `formInstanceOID` |  | nchar(32) | Y |  |
| `processInstanceOID` |  | nchar(32) | Y |  |
| `onlineRead` |  | int | Y |  |
| `conversionState` |  | int | Y |  |

#### `NoCmDocumentAuth` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `noCmDocumentOID` |  | nchar(32) | N |  |
| `noCmDocumentAuthKey` |  | nvarchar(64) | N |  |
| `createdTime` |  | datetime | N |  |
| `noCmDocumentAuthType` |  | nvarchar(2) | N |  |
| `noCmDocumentAuthContent` |  | nvarchar(256) | Y |  |

### 前綴 `Doc` — 文件(Document)（22 表）


#### `DocServer_IDocument` — （無中文名）　(列數約 17,902)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `DocServerOID` |  | nchar(32) | N | PK |
| `DocumentOID` |  | nchar(32) | N | PK |

#### `DocType` — （無中文名）　(列數約 5)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `id` |  | nvarchar(50) | N |  |
| `docTypeName` |  | nvarchar(100) | N |  |
| `superTypeOID` |  | nchar(32) | Y |  |

#### `DocCategoryType` — （無中文名）　(列數約 1)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | Y |  |
| `id` |  | nvarchar(50) | Y |  |
| `name` |  | nvarchar(100) | Y |  |
| `typeAttributes` |  | nvarchar(2000) | Y |  |
| `conditions` |  | nvarchar(2000) | Y |  |
| `headers` |  | nvarchar(2000) | Y |  |

#### `DocCmItem` — （無中文名）　(列數約 1)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `checkInTime` |  | datetime | Y |  |
| `checkoutTime` |  | datetime | Y |  |
| `id` |  | nvarchar(100) | N |  |
| `lastVersion` |  | int | N |  |
| `checkoutUserOID` |  | nchar(32) | Y |  |
| `typeOID` |  | nchar(32) | N |  |

#### `DocServer` — （無中文名）　(列數約 1)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `id` |  | nvarchar(50) | N |  |
| `docServerAddress` |  | nvarchar(50) | N |  |
| `rootDir` |  | nvarchar(100) | N |  |
| `serverType` |  | nvarchar(10) | N |  |
| `containerOID` |  | nchar(32) | N |  |
| `serverProperties` |  | ntext | Y |  |
| `webServerAddress` |  | nvarchar(50) | Y |  |

#### `DocAcsRightRecord` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `userOID` |  | nchar(32) | N |  |
| `docOID` |  | nchar(32) | N |  |
| `startTime` |  | datetime | N |  |
| `endTime` |  | datetime | N |  |
| `processSerialNo` |  | nchar(50) | N |  |
| `formInstanceOID` |  | nchar(32) | N |  |
| `usableSeconds` |  | int | N |  |
| `accessType` |  | int | N |  |

#### `DocCategory` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `cateId` |  | nvarchar(50) | Y |  |
| `objectVersion` |  | int | N |  |
| `categoryName` |  | nvarchar(100) | N |  |
| `superCategoryOID` |  | nchar(32) | Y |  |
| `nameStack` |  | nvarchar(4000) | Y |  |
| `snCode` |  | nvarchar(10) | Y |  |
| `containerOID` |  | nchar(32) | Y |  |

#### `DocCmItem_AccessRight` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `DocCmItemOID` |  | nchar(32) | N | PK |
| `AccessRightOID` |  | nchar(32) | N | PK |

#### `DocCmItem_Category` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `DocCmItemOID` |  | nchar(32) | N | PK |
| `CategoryOID` |  | nchar(32) | N | PK |

#### `DocCmItem_ISODocLevel` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `DocCmItemOID` |  | nchar(32) | N | PK |
| `ISODocLevelOID` |  | nchar(32) | N | PK |

#### `DocCmItem_ISODocType` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `DocCmItemOID` |  | nchar(32) | N | PK |
| `ISODocTypeOID` |  | nchar(32) | N | PK |

#### `DocCmItem_ISOFilePolicy` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `DocCmItemOID` |  | nchar(32) | N | PK |
| `ISOFilePolicyOID` |  | nchar(32) | N | PK |

#### `DocCmItem_RefDoc` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `DocCmItemOID` |  | nchar(32) | N | PK |
| `RefDocOID` |  | nchar(32) | N | PK |

#### `DocDraft` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `description` |  | ntext | Y |  |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `docNo` |  | nvarchar(100) | N | FK? |
| `docName` |  | nvarchar(255) | N |  |
| `createdTime` |  | datetime | N |  |
| `validFrom` |  | datetime | Y |  |

> 隱含關聯：[隱含FK→ docNo→SYN_ISODocCmItem]

#### `DocMetadataDef` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `description` |  | ntext | Y |  |
| `docMetadataDefName` |  | nvarchar(100) | N |  |
| `containerOID` |  | nchar(32) | N |  |

#### `DocMetadataInst` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `value` |  | ntext | Y |  |
| `containerOID` |  | nchar(32) | N |  |
| `descriptiodefinitionOIDn` |  | nchar(32) | N |  |

#### `DocNoReserved` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `SnGenRuleOID` |  | nchar(32) | Y |  |
| `docNo` |  | nvarchar(100) | Y | FK? |
| `applyDate` |  | datetime | Y |  |
| `applierOID` |  | nchar(32) | Y |  |
| `applierName` |  | nvarchar(100) | Y |  |
| `approverOID` |  | nchar(32) | Y |  |
| `approverName` |  | nvarchar(100) | Y |  |
| `actionStatus` |  | nvarchar(100) | Y |  |
| `actionDesc` |  | nvarchar(255) | Y |  |
| `validFrom` |  | datetime | Y |  |
| `authorDate` |  | datetime | Y |  |
| `CategoryOID` |  | nchar(32) | Y |  |
| `ISOTypeOID` |  | nchar(32) | Y |  |
| `ISOLevelOID` |  | nchar(32) | Y |  |

> 隱含關聯：[隱含FK→ docNo→SYN_ISODocCmItem]

#### `Doc_Clause` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `docOID` |  | nchar(32) | N | PK |
| `clauseOID` |  | nchar(32) | N | PK |

#### `Doc_DeployedUnit` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `DocOID` |  | nchar(32) | N | PK |
| `UnitOID` |  | nchar(32) | N | PK |

#### `Doc_Level` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `upperDocOID` |  | nchar(32) | N | PK |
| `lowerDocOID` |  | nchar(32) | N | PK |

#### `Doc_RelatedUnit` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `DocOID` |  | nchar(32) | N | PK |
| `UnitOID` |  | nchar(32) | N | PK |

#### `Documents` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `docNo` |  | nvarchar(100) | N | FK? |
| `docName` |  | nvarchar(255) | N |  |
| `version` |  | int | N |  |
| `authorOID` |  | nchar(32) | N |  |
| `authorName` |  | nvarchar(100) | N |  |
| `createdTime` |  | datetime | N |  |
| `creatUnitOID` |  | nchar(32) | N |  |
| `rsrvUnitOID` |  | nchar(32) | N |  |
| `validFrom` |  | datetime | Y |  |
| `validTo` |  | datetime | Y |  |
| `rsrvTo` |  | datetime | Y |  |
| `changeComment` |  | ntext | Y |  |
| `containerOID` |  | nchar(32) | N |  |
| `description` |  | ntext | Y |  |
| `docStatus` |  | nvarchar(100) | N |  |
| `refProcessInstanceSN` |  | nvarchar(50) | Y |  |
| `requiredToConvertPDF` |  | int | N |  |
| `displayVersion` |  | nvarchar(10) | N |  |
| `pdfSecurityType` |  | nvarchar(50) | N |  |
| `upperDocOID` |  | nchar(32) | Y |  |
| `PDFPassword` |  | nvarchar(20) | Y |  |
| `modifyRequestOID` |  | nchar(32) | Y |  |
| `cancelComment` |  | nvarchar(2000) | Y |  |

> 隱含關聯：[隱含FK→ docNo→SYN_ISODocCmItem]

### 前綴 `SYN` — 同步/整合（33 表）


#### `SYN_Functions` — （無中文名）　(列數約 3,108)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `userId` |  | nvarchar(100) | N | PK |
| `unitId` |  | nvarchar(100) | N | PK |
| `orgId` |  | nvarchar(100) | N | PK |
| `functionName` |  | nvarchar(100) | N |  |
| `isMain` |  | int | N |  |
| `managerId` |  | nvarchar(100) | Y |  |
| `levelName` |  | nvarchar(100) | Y |  |
| `doneSync` |  | int | Y |  |

#### `SYN_Employee` — （無中文名）　(列數約 3,064)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `userId` |  | nvarchar(100) | N | PK |
| `orgId` |  | nvarchar(100) | N | PK |
| `empId` |  | nvarchar(100) | N |  |
| `doneSync` |  | int | Y |  |

#### `SYN_Users` — （無中文名）　(列數約 3,026)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `userId` |  | nvarchar(100) | N | PK |
| `userName` |  | nvarchar(100) | N |  |
| `mailAddress` |  | nvarchar(100) | Y |  |
| `phoneNumber` |  | nvarchar(100) | Y |  |
| `languageType` |  | int | Y |  |
| `leaveDate` |  | datetime | Y |  |
| `enableSubstitute` |  | int | Y |  |
| `ldapid` |  | nvarchar(100) | Y |  |
| `currentType` |  | int | Y |  |
| `doneSync` |  | int | Y |  |

#### `SYN_SubstituteDefinition` — （無中文名）　(列數約 2,177)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `userId` |  | nvarchar(100) | N | PK |
| `substituteId` |  | nvarchar(100) | N | PK |
| `substitutiveOrder` |  | int | Y |  |
| `doneSync` |  | int | Y |  |

#### `SYN_Unit` — （無中文名）　(列數約 392)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `unitId` |  | nvarchar(100) | N | PK |
| `orgId` |  | nvarchar(100) | N | PK |
| `unitName` |  | nvarchar(100) | N |  |
| `unitType` |  | int | Y |  |
| `levelName` |  | nvarchar(100) | Y |  |
| `isValid` |  | int | N |  |
| `doneSync` |  | int | Y |  |

#### `SYN_UnitRelation` — （無中文名）　(列數約 330)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `unitId` |  | nvarchar(100) | N | PK |
| `parentUnitId` |  | nvarchar(100) | N |  |
| `orgId` |  | nvarchar(100) | N | PK |
| `doneSync` |  | int | Y |  |

#### `SYN_UnitManager` — （無中文名）　(列數約 118)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `unitId` |  | nvarchar(100) | N | PK |
| `orgId` |  | nvarchar(100) | N | PK |
| `managerId` |  | nvarchar(100) | N | PK |
| `doneSync` |  | int | Y |  |

#### `SYN_Org` — （無中文名）　(列數約 16)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `orgId` |  | nvarchar(100) | N | PK |
| `orgName` |  | nvarchar(100) | N |  |
| `doneSync` |  | int | Y |  |

#### `SYN_DeployDocServer` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `docNo` |  | nvarchar(100) | N | PK |
| `version` |  | nvarchar(100) | N | PK |
| `docServerId` |  | nvarchar(100) | N | PK |
| `doneSync` |  | int | N |  |

> 隱含關聯：[隱含FK→ docNo→SYN_ISODocCmItem]

#### `SYN_ExtFuncDef` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `defName` |  | nvarchar(100) | N | PK |

#### `SYN_ExtFuncLevel` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `levelName` |  | nvarchar(100) | N | PK |
| `levelValue` |  | int | N |  |

#### `SYN_ExtOrg` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `orgId` |  | nvarchar(100) | N | PK |
| `orgName` |  | nvarchar(100) | Y |  |
| `parentOrgId` |  | nvarchar(100) | N |  |
| `levelName` |  | nvarchar(100) | Y |  |
| `managerId` |  | nvarchar(100) | Y |  |
| `status` |  | nchar(1) | Y |  |

#### `SYN_ExtPartJob` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `userId` |  | nvarchar(100) | N | PK |
| `unitId` |  | nvarchar(100) | N | PK |
| `funcName` |  | nvarchar(100) | Y |  |
| `levelName` |  | nvarchar(100) | Y |  |
| `managerId` |  | nvarchar(100) | Y |  |

#### `SYN_ExtUnitLevel` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `levelName` |  | nvarchar(100) | N | PK |
| `levelValue` |  | int | N |  |

#### `SYN_ExtUser` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `userId` |  | nvarchar(100) | N | PK |
| `userName` |  | nvarchar(100) | Y |  |
| `mailAddress` |  | nvarchar(100) | Y |  |
| `languageType` |  | nvarchar(10) | Y |  |
| `employeeId` |  | nvarchar(100) | Y |  |
| `unitId` |  | nvarchar(100) | Y |  |
| `funcName` |  | nvarchar(100) | Y |  |
| `status` |  | nvarchar(10) | Y |  |
| `ldapid` |  | nvarchar(100) | Y |  |
| `phoneNumber` |  | nvarchar(100) | Y |  |
| `levelName` |  | nvarchar(100) | Y |  |
| `managerId` |  | nvarchar(100) | Y |  |
| `enableSubstitute` |  | nchar(1) | Y |  |
| `substituteId` |  | nvarchar(100) | Y |  |

#### `SYN_FunctionDefinition` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `defName` |  | nvarchar(100) | N | PK |
| `orgId` |  | nvarchar(100) | N | PK |
| `doneSync` |  | int | Y |  |

> 隱含關聯：[隱含FK→ defName→SYN_ExtFuncDef]

#### `SYN_FunctionLevel` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `levelName` |  | nvarchar(100) | N | PK |
| `orgId` |  | nvarchar(100) | N | PK |
| `levelValue` |  | int | N |  |
| `doneSync` |  | int | Y |  |

#### `SYN_Group_User` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `groupId` |  | nvarchar(100) | N | PK |
| `userId` |  | nvarchar(100) | N | PK |
| `orgId` |  | nvarchar(100) | N | PK |
| `doneSync` |  | int | Y |  |

#### `SYN_Groups` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `groupId` |  | nvarchar(100) | N | PK |
| `orgId` |  | nvarchar(100) | N | PK |
| `groupName` |  | nvarchar(100) | N |  |
| `doneSync` |  | int | Y |  |

#### `SYN_ISOAccessRight` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `docNo` |  | nvarchar(100) | N | PK |
| `accessRightId` |  | nvarchar(100) | N | PK |
| `doneSync` |  | int | N |  |

> 隱含關聯：[隱含FK→ docNo→SYN_ISODocCmItem]

#### `SYN_ISOClause` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `docNo` |  | nvarchar(100) | N | PK |
| `version` |  | nvarchar(100) | N | PK |
| `clauseNo` |  | nvarchar(100) | N | PK |
| `doneSync` |  | int | N |  |

> 隱含關聯：[隱含FK→ docNo→SYN_ISODocCmItem]

#### `SYN_ISODocCatergory` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `docNo` |  | nvarchar(100) | N | PK |
| `categoryName` |  | nvarchar(100) | N | PK |
| `doneSync` |  | int | N |  |

> 隱含關聯：[隱含FK→ docNo→SYN_ISODocCmItem]

#### `SYN_ISODocCmItem` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `docNo` |  | nvarchar(100) | N | PK |
| `securityLevelID` |  | nvarchar(100) | N |  |
| `startReadTime` |  | nvarchar(100) | Y |  |
| `endReadTime` |  | nvarchar(100) | Y |  |
| `hoursOfReadable` |  | nvarchar(100) | Y |  |
| `invNodDays` |  | nvarchar(100) | Y |  |
| `waterMarkId` |  | nvarchar(100) | Y |  |
| `vettingId` |  | nvarchar(100) | Y |  |
| `nextVettingDate` |  | nvarchar(100) | Y |  |
| `isNeedSendNotification` |  | nvarchar(100) | Y |  |
| `doneSync` |  | int | N |  |

#### `SYN_ISODocTypeLevel` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `docNo` |  | nvarchar(100) | N | PK |
| `typeID` |  | nvarchar(100) | N | PK |
| `levelID` |  | nvarchar(100) | N | PK |
| `doneSync` |  | int | N |  |

> 隱含關聯：[隱含FK→ docNo→SYN_ISODocCmItem]

#### `SYN_ISODocument` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `docNo` |  | nvarchar(100) | N | PK |
| `docName` |  | nvarchar(100) | N | PK |
| `description` |  | nvarchar(100) | Y |  |
| `version` |  | nvarchar(100) | N | PK |
| `versionIndex` |  | int | Y |  |
| `validFrom` |  | nvarchar(100) | N |  |
| `validTo` |  | nvarchar(100) | Y |  |
| `rsrvTo` |  | nvarchar(100) | Y |  |
| `authorId` |  | nvarchar(100) | N |  |
| `requiredToConvertPDF` |  | nvarchar(100) | N |  |
| `PDFFileSecurityType` |  | nvarchar(100) | N |  |
| `createUnitType` |  | nvarchar(100) | N |  |
| `createUnitOrgID` |  | nvarchar(100) | N |  |
| `createUnitID` |  | nvarchar(100) | N |  |
| `reserveUnitType` |  | nvarchar(100) | N |  |
| `reserveUnitOrgID` |  | nvarchar(100) | N |  |
| `reserveUnitID` |  | nvarchar(100) | N |  |
| `doneSync` |  | int | N |  |

> 隱含關聯：[隱含FK→ docNo→SYN_ISODocCmItem]

#### `SYN_ISODocument_RelatedUnit` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `docNo` |  | nvarchar(100) | N | PK |
| `version` |  | nvarchar(100) | N | PK |
| `relatedUnitType` |  | nvarchar(100) | N |  |
| `relatedUnitOrgID` |  | nvarchar(100) | N | PK |
| `relatedUnitID` |  | nvarchar(100) | N | PK |
| `doneSync` |  | int | N |  |

> 隱含關聯：[隱含FK→ docNo→SYN_ISODocCmItem]

#### `SYN_ISOFile` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `docNo` |  | nvarchar(100) | N | PK |
| `version` |  | nvarchar(100) | N | PK |
| `fileName` |  | nvarchar(100) | N | PK |
| `filePath` |  | nvarchar(100) | N |  |
| `doneSync` |  | int | N |  |

> 隱含關聯：[隱含FK→ docNo→SYN_ISODocCmItem]

#### `SYN_Role` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `roleName` |  | nvarchar(100) | N |  |
| `userId` |  | nvarchar(100) | N | PK |
| `unitId` |  | nvarchar(100) | N | PK |
| `orgId` |  | nvarchar(100) | N | PK |
| `doneSync` |  | int | Y |  |

#### `SYN_RoleDefinition` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `defName` |  | nvarchar(100) | N | PK |
| `orgId` |  | nvarchar(100) | N | PK |
| `doneSync` |  | int | Y |  |

> 隱含關聯：[隱含FK→ defName→SYN_ExtFuncDef]

#### `SYN_Title` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `titleName` |  | nvarchar(100) | N |  |
| `userId` |  | nvarchar(100) | N | PK |
| `unitId` |  | nvarchar(100) | N | PK |
| `orgId` |  | nvarchar(100) | N | PK |
| `doneSync` |  | int | Y |  |

#### `SYN_TitleDefinition` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `defName` |  | nvarchar(100) | N | PK |
| `orgId` |  | nvarchar(100) | N | PK |
| `doneSync` |  | int | Y |  |

> 隱含關聯：[隱含FK→ defName→SYN_ExtFuncDef]

#### `SYN_TrinityBelongDept` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `orgId` |  | nvarchar(100) | Y |  |
| `unitId` |  | nvarchar(100) | Y |  |
| `userId` |  | nvarchar(100) | Y |  |

#### `SYN_UnitLevel` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `levelName` |  | nvarchar(100) | N | PK |
| `orgId` |  | nvarchar(100) | N | PK |
| `levelValue` |  | int | N |  |
| `doneSync` |  | int | Y |  |

### 前綴 `Bam` — —（6 表）


#### `BamActInstData` — （無中文名）　(列數約 5,116)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `limits` |  | real | N |  |
| `isOverTime` |  | int | N |  |
| `processInstanceOID` |  | nchar(32) | N |  |
| `mainProcessInstanceOID` |  | nchar(32) | N |  |
| `activityInstanceOID` |  | nchar(32) | N |  |
| `activityId` |  | nvarchar(100) | N |  |
| `activityName` |  | nvarchar(100) | N |  |
| `mainProcessId` |  | nvarchar(100) | N |  |
| `processId` |  | nvarchar(100) | N |  |
| `createdTime` |  | datetime | N |  |
| `startTime` |  | datetime | N |  |
| `endTime` |  | datetime | N |  |
| `actType` |  | nvarchar(20) | N |  |
| `dealTime` |  | real | N |  |
| `actualDealTime` |  | real | N |  |

#### `BamWorkItemData` — （無中文名）　(列數約 3,635)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `limits` |  | real | N |  |
| `createdTime` |  | datetime | N |  |
| `startTime` |  | datetime | N |  |
| `endTime` |  | datetime | N |  |
| `workItemOID` |  | nchar(32) | N |  |
| `workItemName` |  | nvarchar(100) | N |  |
| `performerOID` |  | nchar(32) | N |  |
| `userId` |  | nvarchar(100) | N |  |
| `userName` |  | nvarchar(100) | N |  |
| `orgUnitId` |  | nvarchar(100) | N |  |
| `mainOUDOID` |  | nchar(32) | N |  |
| `organizationUnitName` |  | nvarchar(100) | N |  |
| `processInstanceOID` |  | nchar(32) | N |  |
| `mainProcessInstanceOID` |  | nchar(32) | N |  |
| `processId` |  | nvarchar(100) | N |  |
| `mainProcessId` |  | nvarchar(100) | N |  |
| `isOverTime` |  | int | N |  |
| `activityInstanceOID` |  | nchar(32) | N |  |
| `activityDefinitionId` |  | nvarchar(100) | N |  |
| `activityName` |  | nvarchar(100) | N |  |
| `dealTime` |  | real | N |  |
| `actualDealTime` |  | real | N |  |

#### `BamProInstData` — （無中文名）　(列數約 1,230)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `isMain` |  | int | N |  |
| `processId` |  | nvarchar(100) | N |  |
| `processInstanceOID` |  | nchar(32) | N |  |
| `mainProcessId` |  | nvarchar(100) | N |  |
| `mainProcessInstanceOID` |  | nchar(32) | N |  |
| `createdTime` |  | datetime | N |  |
| `endTime` |  | datetime | Y |  |
| `subject` |  | ntext | Y |  |
| `requesterOID` |  | nchar(32) | Y |  |
| `requesterId` |  | nvarchar(100) | Y |  |
| `requesterName` |  | nvarchar(100) | Y |  |
| `invokeOrganizationUnitOID` |  | nchar(32) | Y |  |
| `invokeOrganizationUnitId` |  | nvarchar(100) | Y |  |
| `invokeOrganizationUnitName` |  | nvarchar(100) | Y |  |
| `currentState` |  | int | N |  |
| `limits` |  | real | Y |  |
| `serialNumber` |  | nvarchar(100) | Y |  |
| `isOverTime` |  | int | N |  |
| `dealTime` |  | real | Y |  |
| `actualDealTime` |  | real | Y |  |

#### `BamWorkAssignmentData` — （無中文名）　(列數約 47)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `limits` |  | real | N |  |
| `createdTime` |  | datetime | N |  |
| `startTime` |  | datetime | Y |  |
| `workAssignmentOID` |  | nchar(32) | Y |  |
| `workItemOID` |  | nchar(32) | Y |  |
| `workItemName` |  | nvarchar(100) | N |  |
| `performerOID` |  | nchar(32) | N |  |
| `userId` |  | nvarchar(100) | N |  |
| `userName` |  | nvarchar(100) | N |  |
| `orgUnitId` |  | nvarchar(100) | N |  |
| `mainOUDOID` |  | nchar(32) | N |  |
| `organizationUnitName` |  | nvarchar(100) | N |  |
| `processId` |  | nvarchar(100) | N |  |
| `mainProcessId` |  | nvarchar(100) | N |  |
| `processInstanceOID` |  | nchar(32) | N |  |
| `mainProcessInstanceOID` |  | nchar(32) | N |  |
| `subject` |  | ntext | Y |  |
| `serialNumber` |  | nvarchar(100) | Y |  |
| `activityInstanceOID` |  | nchar(32) | Y |  |
| `activityDefinitionId` |  | nvarchar(100) | N |  |
| `activityName` |  | nvarchar(100) | Y |  |

#### `BamProcessRecord` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nvarchar(36) | N | PK |
| `createdTime` |  | datetime | Y |  |
| `processInsOID` |  | nvarchar(32) | Y |  |
| `processDefinitionId` |  | nvarchar(100) | Y |  |
| `processInstanceName` |  | nvarchar(100) | Y |  |
| `serialNumber` |  | nvarchar(100) | Y |  |
| `processCurrentState` |  | int | Y |  |
| `invokeTime` |  | datetime | Y |  |
| `requestId` |  | nvarchar(50) | Y |  |
| `requestName` |  | nvarchar(50) | Y |  |
| `invokeOrgId` |  | nvarchar(50) | Y |  |
| `invokeOrgUnitId` |  | nvarchar(50) | Y |  |
| `invokeOrgUnitName` |  | nvarchar(50) | Y |  |
| `actionTime` |  | datetime | Y |  |
| `actionType` |  | int | Y |  |
| `actionType2` |  | int | Y |  |
| `actionFirstTrigger` |  | int | Y |  |
| `actionActivityId` |  | nvarchar(100) | Y |  |
| `actionActivityPerformer` |  | nvarchar(100) | Y |  |
| `actionIdName` |  | nvarchar(100) | Y |  |
| `newActivityId` |  | nvarchar(100) | Y |  |
| `newPerformerIdName` |  | nvarchar(100) | Y |  |
| `processSubject` |  | nvarchar(500) | Y |  |
| `comments` |  | nvarchar(500) | Y |  |
| `sysCompanyId` |  | nvarchar(100) | Y |  |
| `sysFormNum` |  | nvarchar(100) | Y |  |

#### `BamSetting` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `processDefinitionId` |  | nvarchar(100) | Y |  |
| `beginMonitorTime` |  | datetime | Y |  |
| `lastScheduleRunTime` |  | datetime | Y |  |
| `initialFlag` |  | int | Y |  |

### 前綴 `Con` — —（3 表）


#### `ConditionDefinition` — （無中文名）　(列數約 8,192)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `conditionType` |  | nvarchar(50) | Y |  |
| `objectVersion` |  | int | N |  |
| `content` |  | ntext | Y |  |

#### `ConformanceClass` — （無中文名）　(列數約 1,133)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `conformanceClassType` |  | nvarchar(50) | N |  |

#### `ConnectedUserInfo` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | Y |  |
| `clientIP` |  | nvarchar(100) | Y |  |
| `connectedSessionId` |  | nvarchar(100) | Y |  |
| `connectedTime` |  | bigint | Y |  |
| `loginLocale` |  | nvarchar(32) | Y |  |
| `loginTimeZone` |  | nvarchar(32) | Y |  |
| `loginType` |  | nvarchar(32) | Y |  |
| `userId` |  | nvarchar(100) | Y |  |
| `userName` |  | nvarchar(100) | Y |  |
| `userOID` |  | nchar(32) | N |  |
| `webServerIp` |  | nvarchar(100) | Y |  |
| `webServerPort` |  | nvarchar(32) | Y |  |
| `wfServerId` |  | nvarchar(100) | Y |  |
| `isVip` |  | int | Y |  |
| `loginDeviceInfo` |  | ntext | Y |  |

### 前綴 `Fun` — —（3 表）


#### `FunctionDefinition` — （無中文名）　(列數約 5,780)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `functionDefinitionName` |  | nvarchar(100) | N |  |
| `shortName` |  | nvarchar(100) | Y |  |
| `organizationOID` |  | nchar(32) | Y |  |
| `description` |  | ntext | Y |  |

#### `Functions` — （無中文名）　(列數約 2,589)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `approvalLevelOID` |  | nchar(32) | Y |  |
| `definitionOID` |  | nchar(32) | Y |  |
| `occupantOID` |  | nchar(32) | N |  |
| `organizationUnitOID` |  | nchar(32) | Y |  |
| `specifiedManagerOID` |  | nchar(32) | Y |  |
| `isMain` |  | int | N |  |

#### `FunctionLevel` — （無中文名）　(列數約 178)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `levelValue` |  | int | N |  |
| `functionLevelName` |  | nvarchar(100) | N |  |
| `organizationOID` |  | nchar(32) | N |  |
| `description` |  | ntext | Y |  |

### 前綴 `dfi` — —（3 表）


#### `dfinventory_detail` — （無中文名）　(列數約 7,334)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `dfinvgd_ucount` |  | nvarchar(255) | Y |  |
| `dfinvgd_pcount` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `dfinvgd_unitname` |  | nvarchar(255) | Y |  |
| `dfinvgd_dcount` |  | nvarchar(255) | Y |  |
| `dfinvgd_stuffname` |  | nvarchar(255) | Y |  |
| `dfinvgd_sell` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `dfinvgd_chkcount` |  | nvarchar(255) | Y |  |
| `dfinvgd_code` |  | nvarchar(255) | Y |  |
| `dfinvgd_stock` |  | nvarchar(255) | Y |  |

#### `dfinventory` — （無中文名）　(列數約 111)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `dfinvm_mdydate` |  | nvarchar(255) | Y |  |
| `dfinvm_desc` |  | nvarchar(255) | Y |  |
| `dfinvm_year` |  | nvarchar(255) | Y |  |
| `dfinvm_mdydeptname` |  | nvarchar(255) | Y |  |
| `dfinvm_mdydeptcode` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `dfinvm_username` |  | nvarchar(255) | Y |  |
| `dfinvm_sitename` |  | nvarchar(255) | Y |  |
| `dfinvm_sitecode` |  | nvarchar(255) | Y |  |
| `dfinvm_mdyusercode` |  | nvarchar(255) | Y |  |
| `dfinvm_date` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `dfinvm_mdyusername` |  | nvarchar(255) | Y |  |
| `dfinvm_code` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `dfinvm_adddate` |  | nvarchar(255) | Y |  |
| `dfinvm_month` |  | nvarchar(255) | Y |  |

#### `dfitrequest` — （無中文名）　(列數約 4)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `DT1` |  | datetime | Y |  |
| `RB1` |  | nvarchar(255) | Y |  |
| `DT3` |  | datetime | Y |  |
| `RB3` |  | nvarchar(255) | Y |  |
| `TB1` |  | nvarchar(255) | Y |  |
| `DT2` |  | datetime | Y |  |
| `RB2` |  | nvarchar(255) | Y |  |
| `HT1` |  | nvarchar(255) | Y |  |
| `TA2` |  | nvarchar(255) | Y |  |
| `TB3` |  | nvarchar(255) | Y |  |
| `DT4` |  | datetime | Y |  |
| `RB4` |  | nvarchar(255) | Y |  |
| `TA1` |  | nvarchar(255) | Y |  |
| `TB2` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `TB5` |  | int | Y |  |
| `HT2` |  | nvarchar(255) | Y |  |
| `TB4` |  | nvarchar(255) | Y |  |
| `TB7` |  | nvarchar(255) | Y |  |
| `TB6` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `HT3` |  | nvarchar(255) | Y |  |

### 前綴 `Bas` — —（1 表）


#### `BasicType` — （無中文名）　(列數約 7,076)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `basicTypeType` |  | nvarchar(50) | N |  |

### 前綴 `Use` — 使用者（3 表）


#### `UserLogInOutRecord` — （無中文名）　(列數約 3,518)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | Y |  |
| `clientIP` |  | nvarchar(100) | Y |  |
| `connectedSessionId` |  | nvarchar(100) | Y |  |
| `actionTime` |  | datetime | N |  |
| `actionType` |  | int | N |  |
| `userId` |  | nvarchar(100) | Y |  |
| `userName` |  | nvarchar(100) | Y |  |
| `userOID` |  | nchar(32) | N |  |
| `webServerIp` |  | nvarchar(100) | Y |  |
| `webServerPort` |  | nvarchar(32) | Y |  |
| `wfServerId` |  | nvarchar(100) | Y |  |
| `deviceInfo` |  | nvarchar(2000) | Y |  |

#### `Users` — （無中文名）　(列數約 2,514)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `id` |  | nvarchar(100) | N |  |
| `userName` |  | nvarchar(100) | N |  |
| `objectVersion` |  | int | N |  |
| `password` |  | nvarchar(50) | N |  |
| `leaveDate` |  | datetime | Y |  |
| `referCalendarOID` |  | nchar(32) | Y |  |
| `identificationType` |  | nvarchar(50) | N |  |
| `mailAddress` |  | nvarchar(100) | Y |  |
| `localeString` |  | nvarchar(100) | N |  |
| `phoneNumber` |  | nvarchar(100) | Y |  |
| `workflowServerOID` |  | nchar(32) | Y |  |
| `enableSubstitute` |  | int | N |  |
| `endSubstituteTime` |  | datetime | Y |  |
| `startSubstituteTime` |  | datetime | Y |  |
| `cost` |  | int | Y |  |
| `mailingFrequencyType` |  | int | N |  |
| `ldapid` |  | nvarchar(100) | Y |  |
| `intermissionDate` |  | datetime | Y |  |
| `lastUptPwdDate` |  | datetime | Y |  |
| `userTaskDisplay` |  | int | Y |  |
| `performForwardType` |  | int | Y |  |
| `createdTime` |  | datetime | Y |  |
| `currentType` |  | int | Y |  |
| `passwordWrongTimes` |  | int | Y |  |
| `traceWorkStatus` |  | int | Y |  |

#### `UserName` — （無中文名）　(列數約 3)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `userOID` |  | nchar(32) | Y |  |
| `localeString` |  | nvarchar(5) | N |  |
| `name` |  | nvarchar(100) | N |  |

### 前綴 `dft` — —（4 表）


#### `dftake_detail` — （無中文名）　(列數約 3,183)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `dftakegd_usedname` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `dftakegd_item` |  | nvarchar(255) | Y |  |
| `dftakegd_hdn_useuname` |  | nvarchar(255) | Y |  |
| `dftakegd_useucode` |  | nvarchar(255) | Y |  |
| `dftakegd_count` |  | nvarchar(255) | Y |  |
| `dftakegd_no` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `dftakegd_hdn_usedcode` |  | nvarchar(255) | Y |  |
| `dftakegd_unit` |  | nvarchar(255) | Y |  |
| `dftakegd_meno` |  | nvarchar(255) | Y |  |

#### `dftake` — （無中文名）　(列數約 1,356)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `dftake_hdn_boss` |  | nvarchar(255) | Y |  |
| `dftaked_usedname` |  | nvarchar(255) | Y |  |
| `dftake_hdn_deptcode` |  | nvarchar(255) | Y |  |
| `dftake_appdate` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `dftaked_item` |  | nvarchar(255) | Y |  |
| `dftaked_count` |  | nvarchar(255) | Y |  |
| `dftake_hdn_fdept` |  | nvarchar(255) | Y |  |
| `dftake_dept` |  | nvarchar(255) | Y |  |
| `dftaked_hdn_usedcode` |  | nvarchar(255) | Y |  |
| `dftake_no` |  | nvarchar(255) | Y |  |
| `dftaked_unit` |  | nvarchar(255) | Y |  |
| `dftaked_hdn_useuname` |  | nvarchar(255) | Y |  |
| `dftake_hdn_deptOID` |  | nvarchar(255) | Y |  |
| `dftake_title` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `dftaked_useucode` |  | nvarchar(255) | Y |  |
| `dftake_user` |  | nvarchar(255) | Y |  |
| `dftaked_meno` |  | nvarchar(255) | Y |  |
| `dftake_desc` |  | nvarchar(255) | Y |  |
| `dftake_total` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `dftake_hdn_username` |  | nvarchar(255) | Y |  |

#### `dftest_detail` — （無中文名）　(列數約 211)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `dftakegd_usedname` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `dftakegd_item` |  | nvarchar(255) | Y |  |
| `dftakegd_hdn_useuname` |  | nvarchar(255) | Y |  |
| `dftakegd_useucode` |  | nvarchar(255) | Y |  |
| `dftakegd_count` |  | nvarchar(255) | Y |  |
| `dftakegd_no` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `dftakegd_hdn_usedcode` |  | nvarchar(255) | Y |  |
| `dftakegd_unit` |  | nvarchar(255) | Y |  |
| `dftakegd_meno` |  | nvarchar(255) | Y |  |

#### `dftest` — （無中文名）　(列數約 20)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `dftake_hdn_boss` |  | nvarchar(255) | Y |  |
| `dftaked_usedname` |  | nvarchar(255) | Y |  |
| `dftake_hdn_deptcode` |  | nvarchar(255) | Y |  |
| `dftake_appdate` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `dftaked_item` |  | nvarchar(255) | Y |  |
| `dftaked_count` |  | nvarchar(255) | Y |  |
| `dftake_hdn_fdept` |  | nvarchar(255) | Y |  |
| `dftake_dept` |  | nvarchar(255) | Y |  |
| `dftaked_hdn_usedcode` |  | nvarchar(255) | Y |  |
| `dftake_no` |  | nvarchar(255) | Y |  |
| `dftaked_unit` |  | nvarchar(255) | Y |  |
| `dftaked_hdn_useuname` |  | nvarchar(255) | Y |  |
| `dftake_hdn_deptOID` |  | nvarchar(255) | Y |  |
| `dftake_title` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `dftaked_useucode` |  | nvarchar(255) | Y |  |
| `dftake_user` |  | nvarchar(255) | Y |  |
| `dftaked_meno` |  | nvarchar(255) | Y |  |
| `dftake_desc` |  | nvarchar(255) | Y |  |
| `dftake_total` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `dftake_hdn_username` |  | nvarchar(255) | Y |  |

### 前綴 `Red` — —（1 表）


#### `RedefinableHeader` — （無中文名）　(列數約 3,343)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `authorName` |  | nvarchar(100) | Y |  |
| `codePage` |  | nvarchar(50) | Y |  |
| `countryKey` |  | nvarchar(50) | Y |  |
| `publicationStatus` |  | nvarchar(50) | N |  |
| `objectVersion` |  | int | N |  |
| `version` |  | int | N |  |

### 前綴 `Bpm` — BPM核心（5 表）


#### `BpmGateWay` — （無中文名）　(列數約 1,814)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `objectVersion` |  | int | N |  |
| `OID` |  | nchar(32) | N | PK |

#### `BpmEvent` — （無中文名）　(列數約 1,406)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `id` |  | nvarchar(100) | N |  |
| `objectVersion` |  | int | N |  |
| `eventType` |  | nvarchar(100) | N |  |

#### `BpmActivityMappingDocProp` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `integratedSys` |  | nvarchar(100) | N |  |
| `typeForT` |  | int | N |  |
| `docPropId` |  | nvarchar(100) | N |  |
| `formIds` |  | nvarchar(100) | N |  |
| `code` |  | nvarchar(100) | Y |  |
| `processVersion` |  | int | N |  |
| `processId` |  | nvarchar(100) | N |  |
| `activityId` |  | nvarchar(100) | N |  |
| `fromActivityId` |  | nvarchar(100) | Y |  |
| `containerOID` |  | nchar(32) | N |  |

#### `BpmLane` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `id` |  | nvarchar(100) | N |  |
| `name` |  | nvarchar(100) | N |  |
| `objectVersion` |  | int | N |  |
| `containerOID` |  | nchar(32) | N |  |
| `bpmPoolId` |  | nvarchar(100) | N |  |

#### `BpmPool` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `id` |  | nvarchar(100) | N |  |
| `name` |  | nvarchar(100) | N |  |
| `objectVersion` |  | int | N |  |
| `containerOID` |  | nchar(32) | N |  |

### 前綴 `Ses` — —（1 表）


#### `SessionBeanApplication` — （無中文名）　(列數約 3,053)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | char(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `id` |  | nvarchar(100) | N |  |
| `applicationDefinitionName` |  | nvarchar(100) | Y |  |
| `externalReferenceOID` |  | char(32) | Y |  |
| `isDefault` |  | int | N |  |
| `description` |  | ntext | Y |  |
| `homeClassName` |  | nvarchar(100) | Y |  |
| `jndiName` |  | nvarchar(200) | N |  |
| `methodName` |  | nvarchar(50) | N |  |
| `serverIp` |  | nvarchar(50) | Y |  |
| `serverPort` |  | nvarchar(10) | Y |  |
| `serverType` |  | nvarchar(50) | Y |  |
| `globalApplication` |  | int | Y |  |
| `moduleName` |  | nvarchar(50) | Y |  |
| `serverPrincipal` |  | nvarchar(50) | Y |  |
| `serverCredentials` |  | nvarchar(50) | Y |  |
| `lastExcutingTime` |  | datetime | Y |  |
| `combinationServiceId` |  | nvarchar(100) | Y |  |

### 前綴 `Emp` — —（1 表）


#### `Employee` — （無中文名）　(列數約 2,539)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `employeeId` |  | nvarchar(100) | N |  |
| `organizationOID` |  | nchar(32) | N |  |
| `userOID` |  | nchar(32) | N |  |
| `objectVersion` |  | int | N |  |
| `validTo` |  | datetime | Y |  |

### 前綴 `Rou` — —（1 表）


#### `Route` — （無中文名）　(列數約 2,431)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `objectVersion` |  | int | N |  |
| `OID` |  | char(32) | N | PK |

### 前綴 `Rea` — —（2 表）


#### `ReassignWorkItemAuditData` — （無中文名）　(列數約 2,013)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `aboveProcessInstanceOID` |  | nchar(32) | Y |  |
| `createdTime` |  | datetime | N |  |
| `currentProcessInstanceState` |  | int | N |  |
| `currentProcessInstanceOID` |  | nchar(32) | N |  |
| `currentActivityInstanceOID` |  | nchar(32) | N |  |
| `sourceOID` |  | nchar(32) | N |  |
| `currentWorkItemState` |  | int | N |  |
| `newAssigneeId` |  | nvarchar(100) | N |  |
| `newAssigneeName` |  | nvarchar(100) | N |  |
| `newAssigneeOID` |  | nchar(32) | N |  |
| `oldAssigneeId` |  | nvarchar(100) | N |  |
| `oldAssigneeName` |  | nvarchar(100) | N |  |
| `objectVersion` |  | int | N |  |
| `oldAssigneeOID` |  | nchar(32) | N |  |
| `workAssignmentOID` |  | nchar(32) | N |  |
| `reassignmentType` |  | int | N |  |
| `comments` |  | ntext | Y |  |
| `reassignmentRequester` |  | nvarchar(100) | Y |  |

#### `ReadingRecord` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `docOID` |  | nchar(32) | N |  |
| `docId` |  | nvarchar(100) | N |  |
| `docVersion` |  | int | N |  |
| `userOID` |  | nchar(32) | N |  |
| `userId` |  | nvarchar(100) | N |  |
| `userName` |  | nvarchar(255) | N |  |
| `createdTime` |  | datetime | N |  |
| `action` |  | nvarchar(50) | N |  |
| `isoFileOID` |  | nchar(32) | Y |  |

### 前綴 `Tim` — —（2 表）


#### `TimeEstimation` — （無中文名）　(列數約 1,847)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `duration` |  | real | Y |  |
| `waitingTime` |  | real | Y |  |
| `objectVersion` |  | int | N |  |
| `workingTime` |  | real | Y |  |

#### `TimerWorkSchedule` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `firstTime` |  | datetime | N |  |
| `period` |  | int | N |  |
| `applicationDefinitionId` |  | nvarchar(100) | N |  |
| `parameterValue` |  | nvarchar(255) | Y |  |
| `containerOID` |  | nchar(32) | N |  |

### 前綴 `dfg` — —（1 表）


#### `dfgovernment` — （無中文名）　(列數約 1,505)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `dfcont_title` |  | nvarchar(1000) | Y |  |
| `dfcont_hdn_deptcode` |  | nvarchar(50) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `dfcont_hdn_username` |  | nvarchar(100) | Y |  |
| `dfcont_hdn_deptOID` |  | nvarchar(255) | Y |  |
| `dfcont_usercode` |  | nvarchar(50) | Y |  |
| `dfcont_deptname` |  | nvarchar(100) | Y |  |
| `dfcont_desc` |  | nvarchar(3000) | Y |  |
| `formSerialNumber` |  | nvarchar(100) | Y |  |
| `dfcont_sec` |  | varchar(10) | Y |  |
| `dfcont_date` |  | datetime | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `dfcont_hdn_boss` |  | nvarchar(50) | Y |  |
| `dfcont_hdn_edesc` |  | nvarchar(255) | Y |  |
| `hdndfcont_secname` |  | nvarchar(255) | Y |  |
| `dfcont_no` |  | nvarchar(255) | Y |  |
| `dfcont_usercode_txt` |  | nvarchar(255) | Y |  |
| `deptflow` |  | nvarchar(255) | Y |  |

### 前綴 `dfe` — —（2 表）


#### `dfexpense_detail` — （無中文名）　(列數約 904)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `dfexp_gdtool` |  | nvarchar(255) | Y |  |
| `dfexp_gdsocial` |  | nvarchar(255) | Y |  |
| `dfexp_hdn_gdtoolname` |  | nvarchar(255) | Y |  |
| `dfexp_gdhotel` |  | nvarchar(255) | Y |  |
| `dfexp_gdemile` |  | nvarchar(255) | Y |  |
| `dfexp_gdmix` |  | nvarchar(255) | Y |  |
| `dfexp_gdtype` |  | nvarchar(255) | Y |  |
| `dfexp_hdn_gdtype` |  | nvarchar(255) | Y |  |
| `dfexp_gdsum` |  | nvarchar(255) | Y |  |
| `dfexp_gdeplace` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `dfexp_gdsplace` |  | nvarchar(255) | Y |  |
| `dfexp_gddate` |  | nvarchar(255) | Y |  |
| `dfexp_gdsmile` |  | nvarchar(255) | Y |  |
| `dfexp_gdmeal` |  | nvarchar(255) | Y |  |
| `dfexp_gdfood` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `dfsug_gddesc` |  | nvarchar(255) | Y |  |
| `dfexp_gdtraffic` |  | nvarchar(255) | Y |  |
| `dfexp_gdothfee` |  | nvarchar(255) | Y |  |
| `dfexp_gdno` |  | nvarchar(255) | Y |  |
| `dfexp_gdothitem` |  | nvarchar(255) | Y |  |
| `dfexp_gdmile` |  | nvarchar(255) | Y |  |

#### `dfexpense` — （無中文名）　(列數約 327)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `dfexp_user` |  | nvarchar(255) | Y |  |
| `dfexp_total` |  | float | Y |  |
| `dfexp_prepay` |  | float | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `dfexp_hdn_deptOID` |  | nvarchar(255) | Y |  |
| `dfexp_eplace` |  | nvarchar(255) | Y |  |
| `dfexp_hdn_atool` |  | nvarchar(255) | Y |  |
| `dfexp_deptname` |  | nvarchar(255) | Y |  |
| `dfexp_hdn_deptcode` |  | nvarchar(255) | Y |  |
| `dfexp_mile` |  | float | Y |  |
| `dfexp_traffic` |  | float | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `dfexp_date` |  | datetime | Y |  |
| `dfexp_sum` |  | float | Y |  |
| `dfexp_food` |  | float | Y |  |
| `dfsug_desc` |  | nvarchar(255) | Y |  |
| `dfexp_othitem` |  | nvarchar(255) | Y |  |
| `dfexp_hotel` |  | float | Y |  |
| `dfexp_type` |  | nvarchar(255) | Y |  |
| `dfexp_othfee` |  | float | Y |  |
| `dfexp_hdn_type` |  | nvarchar(255) | Y |  |
| `dfexp_social` |  | float | Y |  |
| `dfexp_emile` |  | float | Y |  |
| `dfexp_mix` |  | float | Y |  |
| `dfexp_meal` |  | float | Y |  |
| `dfexp_hdn_fdept` |  | nvarchar(255) | Y |  |
| `dfexp_hdn_toolname` |  | nvarchar(255) | Y |  |
| `dfexp_hdn_adate` |  | nvarchar(255) | Y |  |
| `dfexp_tool` |  | nvarchar(255) | Y |  |
| `dfexp_pay` |  | float | Y |  |
| `dfexp_hdn_boss` |  | nvarchar(255) | Y |  |
| `dfexp_hdn_aeplace` |  | nvarchar(255) | Y |  |
| `dfexp_smile` |  | float | Y |  |
| `dfexp_hdn_username` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `dfexp_splace` |  | nvarchar(255) | Y |  |
| `dfexp_hdn_atype` |  | nvarchar(255) | Y |  |
| `dfexp_hdn_asplace` |  | nvarchar(255) | Y |  |
| `dfexp_no` |  | nvarchar(255) | Y |  |
| `dfexp_apdate` |  | nvarchar(255) | Y |  |

### 前綴 `Dra` — —（2 表）


#### `Draft` — （無中文名）　(列數約 594)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `creatorOID` |  | nchar(32) | N |  |
| `definitionOID` |  | nchar(32) | N |  |
| `fieldValues` |  | ntext | N |  |
| `formDefinitionId` |  | nvarchar(100) | N |  |
| `containerOID` |  | nchar(32) | N |  |

#### `DraftHeader` — （無中文名）　(列數約 575)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `processVersion` |  | int | N |  |
| `processName` |  | nvarchar(100) | N |  |
| `processPackageOID` |  | nchar(32) | N |  |
| `ownerOID` |  | nchar(32) | N |  |
| `subject` |  | ntext | Y |  |
| `lastSavedTime` |  | datetime | N |  |
| `mobilityProcess` |  | int | N |  |
| `mobilitySignOff` |  | int | Y |  |

### 前綴 `cgs` — —（2 表）


#### `cgsuggest` — （無中文名）　(列數約 994)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `cgsug_no` |  | nvarchar(255) | Y |  |
| `cgsug_hdn_username` |  | nvarchar(255) | Y |  |
| `cgsug_secert` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `cgsug_deptname` |  | nvarchar(255) | Y |  |
| `cgsug_kind` |  | nvarchar(255) | Y |  |
| `cgsug_hdn_deptcode` |  | nvarchar(255) | Y |  |
| `cgsug_advise` |  | nvarchar(max) | Y |  |
| `cgsug_desc` |  | nvarchar(max) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `cgsug_title` |  | nvarchar(1000) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `cgsug_hdn_edesc` |  | nvarchar(255) | Y |  |
| `cgsug_sdate` |  | datetime | Y |  |
| `cgsug_user` |  | nvarchar(255) | Y |  |
| `hdncgsug_bosscode` |  | nvarchar(255) | Y |  |
| `hdncgsug_bossname` |  | nvarchar(255) | Y |  |
| `hdncgsug_deptoid` |  | nvarchar(255) | Y |  |
| `hdncgsug_kindname` |  | nvarchar(255) | Y |  |
| `hdncgsug_secertname` |  | nvarchar(255) | Y |  |
| `hdncgsug_chkfinance` |  | nvarchar(255) | Y |  |
| `txb_amt` |  | float | Y |  |
| `hdncgsug_chkceo` |  | nvarchar(255) | Y |  |
| `hdncgsug_chkmag` |  | nvarchar(255) | Y |  |
| `cgsug_level` |  | nvarchar(255) | Y |  |

#### `cgsuggest__cgsuggest` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | char(32) | N |  |
| `objectVersion` |  | int | N |  |
| `sys_bizModelOID` |  | char(32) | N |  |
| `sys_baseModelOID` |  | char(32) | Y |  |
| `sys_seqOID` |  | char(32) | Y |  |
| `sys_cZmryOID` |  | char(32) | Y |  |
| `sys_containerOID` |  | char(32) | Y |  |
| `sys_prsInsOID` |  | nvarchar(100) | Y |  |
| `sys_createdTime` |  | datetime | Y |  |
| `sys_modifiedTime` |  | datetime | Y |  |
| `sys_lastModifiedUserOID` |  | char(32) | Y |  |
| `sys_creatorOID` |  | char(32) | Y |  |
| `cgsug_user` |  | nvarchar(255) | Y |  |
| `cgsug_user__hi` |  | nvarchar(255) | Y |  |
| `cgsug_user__la` |  | nvarchar(255) | Y |  |
| `cgsug_sdate` |  | datetime | Y |  |
| `cgsug_kind` |  | nvarchar(255) | Y |  |
| `cgsug_secert` |  | nvarchar(255) | Y |  |
| `cgsug_title` |  | nvarchar(255) | Y |  |
| `cgsug_advise` |  | nvarchar(255) | Y |  |
| `cgsug_desc` |  | nvarchar(255) | Y |  |
| `cgsug_hdn_username` |  | nvarchar(255) | Y |  |
| `cgsug_deptname` |  | nvarchar(255) | Y |  |
| `cgsug_hdn_deptcode` |  | nvarchar(255) | Y |  |
| `cgsug_hdn_edesc` |  | nvarchar(255) | Y |  |
| `hdncgsug_bosscode` |  | nvarchar(255) | Y |  |
| `hdncgsug_bossname` |  | nvarchar(255) | Y |  |
| `hdncgsug_deptoid` |  | nvarchar(255) | Y |  |
| `SerialNumber` |  | nvarchar(255) | N |  |
| `hdncgsug_secertname` |  | nvarchar(255) | Y |  |
| `hdncgsug_kindname` |  | nvarchar(255) | Y |  |
| `cgsug_level` |  | nvarchar(255) | Y |  |
| `hdncgsug_chkfinance` |  | nvarchar(255) | Y |  |
| `hdncgsug_chkmag` |  | nvarchar(255) | Y |  |
| `hdncgsug_chkceo` |  | nvarchar(255) | Y |  |
| `txb_amt` |  | float | Y |  |

### 前綴 `Pac` — —（2 表）


#### `PackageInvokeAuthority` — （無中文名）　(列數約 903)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `userList` |  | ntext | Y |  |
| `organizationUnitList` |  | ntext | Y |  |
| `objectVersion` |  | int | N |  |
| `groupList` |  | ntext | Y |  |
| `functionDefList` |  | ntext | Y |  |

#### `PackageCategoryAccessRight` — （無中文名）　(列數約 2)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `rightType` |  | int | N |  |
| `categoryOID` |  | nchar(32) | N |  |
| `ownerId` |  | nvarchar(100) | N |  |
| `organizationId` |  | nvarchar(100) | N |  |
| `includeSubCate` |  | int | N |  |

### 前綴 `dfw` — —（2 表）


#### `dfwaorder_detail` — （無中文名）　(列數約 416)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `dfwaorder_gdsum` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `dfwaorder_gdoprice` |  | nvarchar(255) | Y |  |
| `dfwaorder_gdno` |  | nvarchar(255) | Y |  |
| `dfwaorder_gdgname` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `dfwaorder_hdn_gdgcode` |  | nvarchar(255) | Y |  |
| `dfwaorder_gdcount` |  | nvarchar(255) | Y |  |
| `dfwaorder_gdunit` |  | nvarchar(255) | Y |  |

#### `dfwaorder` — （無中文名）　(列數約 218)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `dfwaorder_deptname` |  | nvarchar(255) | Y |  |
| `dfwaorder_total` |  | float | Y |  |
| `dfwaorder_hdn_boss` |  | nvarchar(255) | Y |  |
| `dfwaorder_oprice` |  | float | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `dfwaorder_hdn_username` |  | nvarchar(255) | Y |  |
| `dfwaorder_unit` |  | nvarchar(255) | Y |  |
| `dfwaorder_appdate` |  | nvarchar(255) | Y |  |
| `dfwaorder_hdn_deptcode` |  | nvarchar(255) | Y |  |
| `dfwaorder_takedesc` |  | nvarchar(255) | Y |  |
| `dfwaorder_take` |  | nvarchar(255) | Y |  |
| `dfwaorder_tax` |  | float | Y |  |
| `dfwaorder_title` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `dfwaorder_desc` |  | nvarchar(255) | Y |  |
| `dfwaorder_gname` |  | nvarchar(255) | Y |  |
| `dfwaorder_hdn_gcode` |  | nvarchar(255) | Y |  |
| `dfwaorder_hdn_deptOID` |  | nvarchar(255) | Y |  |
| `dfwaorder_user` |  | nvarchar(255) | Y |  |
| `dfwaorder_sum` |  | float | Y |  |
| `dfwaorder_count` |  | float | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `dfwaorder_money` |  | float | Y |  |
| `dfwaorder_no` |  | nvarchar(255) | Y |  |
| `dfwaorder_takename` |  | nvarchar(255) | Y |  |

### 前綴 `MLA` — —（2 表）


#### `MLANGUAGE` — （無中文名）　(列數約 502)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `oid` |  | nchar(32) | N | PK |
| `group_type` |  | nvarchar(32) | Y |  |
| `group_id` |  | nvarchar(32) | Y |  |
| `field_id` |  | nvarchar(32) | Y |  |
| `zh_CN` |  | nvarchar(255) | Y |  |
| `zh_TW` |  | nvarchar(255) | Y |  |
| `en_US` |  | nvarchar(255) | Y |  |
| `creator` |  | nvarchar(255) | Y |  |
| `create_time` |  | datetime | Y |  |
| `RES04` |  | nvarchar(255) | Y |  |
| `RES05` |  | nvarchar(255) | Y |  |
| `RES06` |  | nvarchar(255) | Y |  |
| `RES07` |  | nvarchar(255) | Y |  |
| `RES08` |  | nvarchar(255) | Y |  |

#### `MLANGUAGE_RELATION` — （無中文名）　(列數約 3)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `oid` |  | nchar(32) | N | PK |
| `language_id` |  | nvarchar(255) | Y |  |
| `display_name` |  | nvarchar(255) | Y |  |
| `field_value` |  | nvarchar(255) | Y |  |
| `creator` |  | nvarchar(32) | Y |  |
| `create_time` |  | datetime | Y |  |
| `upload_status` |  | numeric(8,0) | Y |  |

### 前綴 `Org` — 組織(Org)（6 表）


#### `OrganizationUnit` — （無中文名）　(列數約 325)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `id` |  | nvarchar(100) | N |  |
| `organizationUnitName` |  | nvarchar(100) | N |  |
| `managerOID` |  | nchar(32) | Y |  |
| `superUnitOID` |  | nchar(32) | Y |  |
| `objectVersion` |  | int | N |  |
| `organizationUnitType` |  | int | N |  |
| `levelOID` |  | nchar(32) | Y |  |
| `organizationOID` |  | nchar(32) | N |  |
| `validType` |  | int | N |  |

#### `OrganizationUnitLevel` — （無中文名）　(列數約 105)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `levelValue` |  | int | N |  |
| `organizationUnitLevelName` |  | nvarchar(100) | N |  |
| `organizationOID` |  | nchar(32) | N |  |
| `description` |  | ntext | Y |  |

#### `Organization` — （無中文名）　(列數約 59)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `id` |  | nvarchar(100) | N |  |
| `objectVersion` |  | int | N |  |
| `organizationName` |  | nvarchar(100) | N |  |

#### `OrgWizardAuthorityScope` — （無中文名）　(列數約 6)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `isIncludeSubUnit` |  | int | N |  |
| `scopeOID` |  | nchar(32) | Y |  |
| `scopeType` |  | nvarchar(100) | N |  |
| `ownerId` |  | nvarchar(100) | N |  |
| `organizationId` |  | nvarchar(100) | N |  |

#### `OrganizationUnitProperty` — （無中文名）　(列數約 2)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `organizationUnitPropertyName` |  | nvarchar(100) | N |  |
| `description` |  | ntext | Y |  |
| `organizationOID` |  | nchar(32) | Y |  |

#### `OrgUnit_OrgUnitProperty` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OrganizationUnitPropertyOID` |  | nchar(32) | N | PK |
| `OrganizationUnitOID` |  | nchar(32) | N | PK |

### 前綴 `Nos` — —（1 表）


#### `Nos` — （無中文名）　(列數約 442)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `containerOID` |  | nchar(32) | Y |  |
| `noIndex` |  | int | N |  |

### 前綴 `Mob` — —（9 表）


#### `MobileOAuthWeChatUser` — （無中文名）　(列數約 395)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | char(32) | N |  |
| `objectVersion` |  | int | N |  |
| `UserOID` |  | nvarchar(32) | N |  |
| `WeChatID` |  | nvarchar(32) | Y |  |
| `WiXinID` |  | nvarchar(32) | Y |  |
| `Enable` |  | int | N |  |
| `Auth` |  | int | N |  |
| `OAuthConfigOID` |  | char(32) | N |  |
| `LastLoginTime` |  | datetime | Y |  |
| `RemoteData` |  | ntext | Y |  |

#### `MobileScheduleRecord` — （無中文名）　(列數約 2)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | char(32) | N |  |
| `objectVersion` |  | int | N |  |
| `WorkItemOID` |  | char(32) | N |  |
| `ScheduleID` |  | nvarchar(32) | N |  |
| `ScheduleStatus` |  | int | N |  |
| `ScheduleTitle` |  | nvarchar(64) | N |  |
| `ScheduleReservationTime` |  | datetime | N |  |
| `ScheduleStorageTime` |  | datetime | N |  |
| `ScheduleOuterID` |  | nvarchar(1024) | Y |  |

#### `MobileOAuthConfig` — （無中文名）　(列數約 1)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | char(32) | N |  |
| `objectVersion` |  | int | N |  |
| `OAuthID` |  | nvarchar(128) | N |  |
| `OAuthSecret` |  | nvarchar(128) | N |  |
| `OAuthAlias` |  | nvarchar(256) | N |  |
| `OAuthType` |  | int | N |  |
| `OAuthServiceURL` |  | nvarchar(256) | N |  |
| `OAuthAPIURL` |  | nvarchar(256) | N |  |
| `OAuthServiceAngent` |  | nvarchar(128) | Y |  |
| `OAuthTokenExpire` |  | int | N |  |
| `OAuthPushType` |  | int | Y |  |
| `OAuthAPISecret` |  | nvarchar(256) | N |  |
| `OAuthStatistical` |  | text | Y |  |
| `OAuthPlatformServiceType` |  | int | Y |  |
| `OAuthTenantId` |  | nvarchar(256) | Y |  |
| `OAuthIntegratedId` |  | nvarchar(256) | Y |  |
| `OAuthAuthorizedInfo` |  | text | Y |  |

#### `MobileCallBackConfig` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | char(32) | N |  |
| `objectVersion` |  | int | Y |  |
| `OAuthConfigOID` |  | char(32) | N |  |
| `OAuthCallBackToken` |  | nvarchar(128) | N |  |
| `OAuthCallBackEncryptKey` |  | nvarchar(128) | N |  |

#### `MobileDynamicFormRecord` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | char(32) | N |  |
| `objectVersion` |  | int | N |  |
| `applicationId` |  | nvarchar(128) | N |  |
| `formId` |  | nvarchar(100) | N |  |
| `versionSn` |  | nvarchar(64) | N |  |
| `orderIndex` |  | int | Y |  |

#### `MobileGraphTemplates` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | char(32) | N |  |
| `objectVersion` |  | int | N |  |
| `Content` |  | text | N |  |
| `CreateTime` |  | datetime | N |  |

#### `MobileMessageSubscription` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | char(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `userOID` |  | nvarchar(32) | N |  |
| `processDefinitionId` |  | nvarchar(100) | N |  |
| `status` |  | int | N |  |

#### `MobileOAuthWeChatOrganization` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | char(32) | N |  |
| `objectVersion` |  | int | N |  |
| `OrganizationOID` |  | varchar(32) | N |  |
| `OrganizationName` |  | nvarchar(128) | N |  |
| `WeChatOrganizationID` |  | int | N |  |
| `WeChatOrganizationName` |  | nvarchar(128) | N |  |
| `WeChatOrganizationPID` |  | varchar(32) | N |  |
| `OAuthConfigOID` |  | char(32) | N |  |

#### `MobileSyncOrgConfig` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | char(32) | N |  |
| `objectVersion` |  | int | N |  |
| `SyncROOTID` |  | nvarchar(2) | N |  |
| `SyncROOTName` |  | nvarchar(64) | N |  |
| `OAuthConfigOID` |  | char(32) | N |  |

### 前綴 `Res` — —（4 表）


#### `ResponsibleDefinition` — （無中文名）　(列數約 362)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `responsibleId` |  | nvarchar(100) | N |  |
| `objectVersion` |  | int | N |  |
| `containerOID` |  | nchar(32) | Y |  |
| `invokeOrgOID` |  | nchar(32) | Y |  |

#### `Resignation` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `ownerOID` |  | nchar(32) | N |  |
| `resignerOID` |  | nchar(32) | N |  |

#### `Resources` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `id` |  | nvarchar(100) | N |  |
| `objectVersion` |  | int | N |  |
| `resourceName` |  | nvarchar(100) | N |  |
| `organizationOID` |  | nchar(32) | N |  |

#### `RestfulApplication` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `id` |  | nvarchar(100) | N |  |
| `applicationDefinitionName` |  | nvarchar(100) | Y |  |
| `externalReferenceOID` |  | nchar(32) | Y |  |
| `globalApplication` |  | int | Y |  |
| `description` |  | ntext | Y |  |
| `isDefault` |  | int | N |  |
| `restfulUrl` |  | nvarchar(400) | N |  |
| `verification` |  | int | N |  |

### 前綴 `afa` — —（4 表）


#### `afat102_s_fat` — （無中文名）　(列數約 164)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nvarchar(255) | N | PK |
| `fat09` |  | nvarchar(255) | Y |  |
| `faj06` |  | nvarchar(255) | Y |  |
| `fat07` |  | nvarchar(255) | Y |  |
| `fat08` |  | nvarchar(255) | Y |  |
| `ef_gem02` |  | nvarchar(255) | Y |  |
| `fat11` |  | nvarchar(255) | Y |  |
| `fat02` |  | nvarchar(255) | Y |  |
| `fat10` |  | nvarchar(255) | Y |  |
| `fat04` |  | nvarchar(255) | Y |  |
| `fat03` |  | nvarchar(255) | Y |  |
| `fat06` |  | nvarchar(255) | Y |  |
| `fat05` |  | nvarchar(255) | Y |  |
| `fat031` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `fatud05` |  | nvarchar(255) | Y |  |
| `fatud04` |  | nvarchar(255) | Y |  |
| `fatud03` |  | nvarchar(255) | Y |  |
| `fatud02` |  | nvarchar(255) | Y |  |

#### `afat102` — （無中文名）　(列數約 106)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `fas06` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `fas07` |  | nvarchar(255) | Y |  |
| `fas04` |  | nvarchar(255) | Y |  |
| `fas05` |  | nvarchar(255) | Y |  |
| `fas02` |  | nvarchar(255) | Y |  |
| `gem02` |  | nvarchar(255) | Y |  |
| `fas03` |  | nvarchar(255) | Y |  |
| `faspost` |  | nvarchar(255) | Y |  |
| `fas01` |  | nvarchar(255) | Y |  |
| `gen02` |  | nvarchar(255) | Y |  |
| `fag03` |  | nvarchar(255) | Y |  |
| `hdnafat102_fat04` |  | nvarchar(255) | Y |  |
| `hdnafat102_fas04_fcode` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `fas08` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `hd_tb_trantype` |  | nvarchar(255) | Y |  |
| `fasud01` |  | nvarchar(255) | Y |  |
| `fasud02` |  | nvarchar(255) | Y |  |
| `lvpeople` |  | nvarchar(255) | Y |  |

#### `afat108` — （無中文名）　(列數約 21)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nvarchar(255) | N | PK |
| `gem02` |  | nvarchar(255) | Y |  |
| `hdnafat108_fbh06` |  | nvarchar(255) | Y |  |
| `fbg09` |  | nvarchar(255) | Y |  |
| `fbg08` |  | nvarchar(255) | Y |  |
| `gen02` |  | nvarchar(255) | Y |  |
| `fbg05` |  | nvarchar(255) | Y |  |
| `fbg03` |  | nvarchar(255) | Y |  |
| `fbg04` |  | nvarchar(255) | Y |  |
| `fbg01` |  | nvarchar(255) | Y |  |
| `fbgpost` |  | nvarchar(255) | Y |  |
| `fbg02` |  | nvarchar(255) | Y |  |
| `fbgud01` |  | nvarchar(255) | Y |  |
| `fbgpost2` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |

#### `afat108_s_fbh` — （無中文名）　(列數約 21)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `fbh07` |  | nvarchar(255) | Y |  |
| `fbh06` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `fbh05` |  | nvarchar(255) | Y |  |
| `fbh04` |  | nvarchar(255) | Y |  |
| `fbh08` |  | nvarchar(255) | Y |  |
| `faj18` |  | nvarchar(255) | Y |  |
| `faj06` |  | nvarchar(255) | Y |  |
| `fbh12` |  | nvarchar(255) | Y |  |
| `fbh02` |  | nvarchar(255) | Y |  |
| `fbh03` |  | nvarchar(255) | Y |  |
| `fbh031` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |

### 前綴 `aap` — —（4 表）


#### `aapt120_s_apb` — （無中文名）　(列數約 157)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nvarchar(255) | N | PK |
| `apb24` |  | nvarchar(255) | Y |  |
| `apb23` |  | nvarchar(255) | Y |  |
| `apb26` |  | nvarchar(255) | Y |  |
| `apb08` |  | nvarchar(255) | Y |  |
| `apb09` |  | nvarchar(255) | Y |  |
| `apb10` |  | nvarchar(255) | Y |  |
| `apb28` |  | nvarchar(255) | Y |  |
| `ta_apb002` |  | nvarchar(255) | Y |  |
| `apb27` |  | nvarchar(255) | Y |  |
| `apb12` |  | nvarchar(255) | Y |  |
| `b26` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `ta_apb003` |  | nvarchar(255) | Y |  |

#### `aapt120` — （無中文名）　(列數約 100)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `apo02` |  | nvarchar(255) | Y |  |
| `apainpd` |  | nvarchar(255) | Y |  |
| `apr02` |  | nvarchar(255) | Y |  |
| `apaud02` |  | nvarchar(255) | Y |  |
| `apa61f` |  | nvarchar(255) | Y |  |
| `apa34` |  | nvarchar(255) | Y |  |
| `apa33` |  | nvarchar(255) | Y |  |
| `apa32` |  | nvarchar(255) | Y |  |
| `apa31` |  | nvarchar(255) | Y |  |
| `apa36` |  | nvarchar(255) | Y |  |
| `apa35` |  | nvarchar(255) | Y |  |
| `gem02` |  | nvarchar(255) | Y |  |
| `apa100` |  | nvarchar(255) | Y |  |
| `apa55` |  | nvarchar(255) | Y |  |
| `apa65f` |  | nvarchar(255) | Y |  |
| `apa56` |  | nvarchar(255) | Y |  |
| `apa57` |  | nvarchar(255) | Y |  |
| `apa58` |  | nvarchar(255) | Y |  |
| `apa35_uf` |  | nvarchar(255) | Y |  |
| `apa21` |  | nvarchar(255) | Y |  |
| `apa60f` |  | nvarchar(255) | Y |  |
| `apa20` |  | nvarchar(255) | Y |  |
| `apa35_u` |  | nvarchar(255) | Y |  |
| `apa22` |  | nvarchar(255) | Y |  |
| `apa25` |  | nvarchar(255) | Y |  |
| `apa24` |  | nvarchar(255) | Y |  |
| `apa32f` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `net` |  | nvarchar(255) | Y |  |
| `apa66` |  | nvarchar(255) | Y |  |
| `gen02` |  | nvarchar(255) | Y |  |
| `apa64` |  | nvarchar(255) | Y |  |
| `apa65` |  | nvarchar(255) | Y |  |
| `apa61` |  | nvarchar(255) | Y |  |
| `apa60` |  | nvarchar(255) | Y |  |
| `apa31f` |  | nvarchar(255) | Y |  |
| `apa19` |  | nvarchar(255) | Y |  |
| `apa56_name` |  | nvarchar(255) | Y |  |
| `apa16` |  | nvarchar(255) | Y |  |
| `apa15` |  | nvarchar(255) | Y |  |
| `apa14` |  | nvarchar(255) | Y |  |
| `apa13` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `apa12` |  | nvarchar(255) | Y |  |
| `pmc03` |  | nvarchar(255) | Y |  |
| `apa11` |  | nvarchar(255) | Y |  |
| `apa35f` |  | nvarchar(255) | Y |  |
| `TbAmt` |  | nvarchar(255) | Y |  |
| `apa07` |  | nvarchar(255) | Y |  |
| `apa06` |  | nvarchar(255) | Y |  |
| `apa08` |  | nvarchar(255) | Y |  |
| `pma11` |  | nvarchar(255) | Y |  |
| `apa02` |  | nvarchar(255) | Y |  |
| `apa05` |  | nvarchar(255) | Y |  |
| `apa34f` |  | nvarchar(255) | Y |  |
| `apa01` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `apaud03` |  | nvarchar(255) | Y |  |

#### `aapt120__aapt120` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | char(32) | N |  |
| `objectVersion` |  | int | N |  |
| `sys_bizModelOID` |  | char(32) | N |  |
| `sys_baseModelOID` |  | char(32) | Y |  |
| `sys_seqOID` |  | char(32) | Y |  |
| `sys_cZmryOID` |  | char(32) | Y |  |
| `sys_containerOID` |  | char(32) | Y |  |
| `sys_prsInsOID` |  | nvarchar(100) | Y |  |
| `sys_createdTime` |  | datetime | Y |  |
| `sys_modifiedTime` |  | datetime | Y |  |
| `sys_lastModifiedUserOID` |  | char(32) | Y |  |
| `sys_creatorOID` |  | char(32) | Y |  |
| `pmc03` |  | nvarchar(255) | Y |  |
| `gen02` |  | nvarchar(255) | Y |  |
| `apa07` |  | nvarchar(255) | Y |  |
| `apa01` |  | nvarchar(255) | Y |  |
| `apa05` |  | nvarchar(255) | Y |  |
| `apa21` |  | nvarchar(255) | Y |  |
| `apa06` |  | nvarchar(255) | Y |  |
| `apa22` |  | nvarchar(255) | Y |  |
| `apa02` |  | nvarchar(255) | Y |  |
| `apr02` |  | nvarchar(255) | Y |  |
| `apa08` |  | nvarchar(255) | Y |  |
| `apa16` |  | float | Y |  |
| `apa36` |  | nvarchar(255) | Y |  |
| `apa13` |  | nvarchar(255) | Y |  |
| `apa14` |  | float | Y |  |
| `apa15` |  | nvarchar(255) | Y |  |
| `apa58` |  | nvarchar(255) | Y |  |
| `apa24` |  | nvarchar(255) | Y |  |
| `apa11` |  | nvarchar(255) | Y |  |
| `apa12` |  | nvarchar(255) | Y |  |
| `apa64` |  | nvarchar(255) | Y |  |
| `pma11` |  | nvarchar(255) | Y |  |
| `apa55` |  | nvarchar(255) | Y |  |
| `apa31f` |  | float | Y |  |
| `apa60f` |  | float | Y |  |
| `apa31` |  | float | Y |  |
| `apa60` |  | float | Y |  |
| `apa32f` |  | float | Y |  |
| `apa61f` |  | float | Y |  |
| `apa32` |  | float | Y |  |
| `apa61` |  | float | Y |  |
| `apa65f` |  | float | Y |  |
| `apa65` |  | float | Y |  |
| `apa34f` |  | float | Y |  |
| `apa34` |  | float | Y |  |
| `apa35f` |  | float | Y |  |
| `apa35` |  | float | Y |  |
| `apa35_uf` |  | float | Y |  |
| `apa35_u` |  | float | Y |  |
| `net` |  | float | Y |  |
| `apo02` |  | nvarchar(255) | Y |  |
| `apa20` |  | float | Y |  |
| `apa19` |  | nvarchar(255) | Y |  |
| `apa56_name` |  | nvarchar(255) | Y |  |
| `apa33` |  | float | Y |  |
| `apa25` |  | nvarchar(255) | Y |  |
| `apa66` |  | nvarchar(255) | Y |  |
| `apa56` |  | nvarchar(255) | Y |  |
| `apainpd` |  | nvarchar(255) | Y |  |
| `apa57` |  | float | Y |  |
| `gem02` |  | nvarchar(255) | Y |  |
| `apa100` |  | nvarchar(255) | Y |  |
| `TbAmt` |  | int | Y |  |
| `apaud02` |  | nvarchar(255) | Y |  |
| `SerialNumber` |  | nvarchar(255) | N |  |

#### `aapt120__s_apb` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | char(32) | N |  |
| `objectVersion` |  | int | N |  |
| `sys_bizModelOID` |  | char(32) | Y |  |
| `sys_baseModelOID` |  | char(32) | Y |  |
| `sys_seqOID` |  | char(32) | Y |  |
| `sys_cZmryOID` |  | char(32) | Y |  |
| `sys_containerOID` |  | char(32) | N |  |
| `sys_prsInsOID` |  | nvarchar(100) | Y |  |
| `sys_createdTime` |  | datetime | Y |  |
| `sys_modifiedTime` |  | datetime | Y |  |
| `sys_lastModifiedUserOID` |  | char(32) | Y |  |
| `sys_creatorOID` |  | char(32) | Y |  |
| `apb02` |  | nvarchar(5) | Y |  |
| `apb12` |  | nvarchar(255) | Y |  |
| `apb27` |  | nvarchar(255) | Y |  |
| `apb09` |  | nvarchar(255) | Y |  |
| `apb28` |  | nvarchar(10) | Y |  |
| `apb26` |  | nvarchar(255) | Y |  |
| `b26` |  | nvarchar(255) | Y |  |
| `apb23` |  | nvarchar(255) | Y |  |
| `apb24` |  | nvarchar(255) | Y |  |
| `apb08` |  | nvarchar(255) | Y |  |
| `apb10` |  | nvarchar(255) | Y |  |

### 前綴 `dfb` — —（1 表）


#### `dfbasedata` — （無中文名）　(列數約 254)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `hdndfsug_secertname` |  | nvarchar(255) | Y |  |
| `hdndfsug_kindname` |  | nvarchar(255) | Y |  |
| `dfsug_desc` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `dfsug_secert` |  | nvarchar(255) | Y |  |
| `dfsug_user` |  | nvarchar(255) | Y |  |
| `hdnFilePath` |  | nvarchar(255) | Y |  |
| `dfsug_no` |  | nvarchar(255) | Y |  |
| `dfsug_hdn_username` |  | nvarchar(255) | Y |  |
| `dfsug_hdn_edesc` |  | nvarchar(255) | Y |  |
| `dfsug_title` |  | nvarchar(255) | Y |  |
| `dfsug_sdate` |  | datetime | Y |  |
| `dfsug_hdn_deptcode` |  | nvarchar(255) | Y |  |
| `dfsug_kind` |  | nvarchar(255) | Y |  |
| `dfsug_deptname` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |

### 前綴 `Ins` — —（1 表）


#### `InstanceSerialNumber` — （無中文名）　(列數約 250)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `definitionId` |  | nvarchar(100) | N |  |
| `lastNumber` |  | int | N |  |
| `objectVersion` |  | int | N |  |
| `prefixValue` |  | nvarchar(100) | Y |  |
| `serialNumberType` |  | int | N |  |

### 前綴 `Sys` — 系統設定（7 表）


#### `SystemVariable` — （無中文名）　(列數約 240)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `sysKey` |  | nvarchar(256) | N |  |
| `value` |  | ntext | Y |  |
| `description` |  | ntext | Y |  |
| `updateTime` |  | datetime | N |  |
| `updaterOID` |  | nchar(32) | N |  |
| `manual` |  | char(1) | Y |  |
| `formatSTR` |  | nvarchar(256) | Y |  |
| `originalKey` |  | nvarchar(256) | Y |  |
| `propertiesFileName` |  | nvarchar(128) | Y |  |

#### `SysLanguage` — （無中文名）　(列數約 4)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `localeString` |  | nvarchar(100) | N |  |
| `displayName` |  | nvarchar(100) | N |  |
| `description` |  | nvarchar(1000) | Y |  |
| `createrOID` |  | nchar(32) | N |  |
| `createdTime` |  | datetime | N |  |

#### `SysT100Config` — （無中文名）　(列數約 1)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `creatorKey` |  | nvarchar(50) | Y |  |
| `mainDept` |  | int | N |  |
| `statusUpdateWithForm` |  | int | N |  |
| `reexecuteFirstActAction` |  | int | Y |  |

#### `SystemConfig` — （無中文名）　(列數約 1)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `verifyPasswordType` |  | nvarchar(50) | N |  |
| `mailServerAddress` |  | nvarchar(128) | Y |  |
| `mailServerAccount` |  | nvarchar(50) | Y |  |
| `mailServerPwd` |  | nvarchar(50) | Y |  |
| `mailNoticeEnable` |  | int | N |  |
| `mailingFrequencyType` |  | int | N |  |
| `ldapCfgSet` |  | ntext | Y |  |
| `defaultSender` |  | nvarchar(100) | Y |  |
| `mailServerType` |  | nvarchar(50) | N |  |
| `mailPort` |  | nvarchar(50) | Y |  |

#### `SysTiptopMappingKey` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `integratedSys` |  | nvarchar(255) | N |  |
| `createdTime` |  | datetime | N |  |
| `processSerialNumber` |  | nvarchar(100) | Y |  |
| `status` |  | nvarchar(2) | N |  |
| `entId` |  | nvarchar(50) | N |  |
| `companyId` |  | nvarchar(50) | Y |  |
| `docProp` |  | nvarchar(50) | Y |  |
| `refId` |  | nvarchar(200) | Y |  |
| `prog` |  | nvarchar(50) | Y |  |
| `formId` |  | nvarchar(20) | Y |  |
| `sheetNo` |  | nvarchar(50) | Y |  |
| `pk3` |  | nvarchar(50) | Y |  |
| `docKey` |  | nvarchar(255) | N |  |
| `progUrl` |  | nvarchar(255) | Y |  |
| `attachUrl` |  | nvarchar(255) | Y |  |
| `acctId` |  | nvarchar(50) | N |  |
| `ownerId` |  | nvarchar(50) | N |  |
| `wfProcessSerialNumber` |  | nvarchar(100) | Y |  |

#### `SysintegrationServer` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `integratedSys` |  | nvarchar(50) | N |  |
| `sysIp` |  | nvarchar(50) | Y |  |
| `sysPort` |  | nvarchar(10) | N |  |
| `entId` |  | nvarchar(10) | N |  |
| `serviceId` |  | nvarchar(10) | N |  |
| `sysDesc` |  | nvarchar(max) | Y |  |
| `serviceProd` |  | nvarchar(50) | Y |  |
| `serviceUrl` |  | nvarchar(100) | Y |  |
| `webService` |  | nvarchar(150) | Y |  |
| `isValid` |  | int | Y |  |
| `creatorOID` |  | nchar(32) | Y |  |
| `createdTime` |  | datetime | Y |  |
| `updaterOID` |  | nchar(32) | Y |  |
| `updateTime` |  | datetime | Y |  |
| `docCenterApiUrl` |  | nvarchar(200) | Y |  |

#### `SysintegrationUsers` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `sysintegrationServerOID` |  | nchar(32) | Y |  |
| `userOID` |  | nchar(32) | Y |  |
| `account` |  | nvarchar(100) | Y |  |
| `creatorOID` |  | nchar(32) | Y |  |
| `createdTime` |  | datetime | Y |  |
| `updaterOID` |  | nchar(32) | Y |  |
| `updateTime` |  | datetime | Y |  |

### 前綴 `Mai` — —（3 表）


#### `Mails` — （無中文名）　(列數約 217)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `receiverOID` |  | nchar(32) | N |  |
| `mailingFrequencyType` |  | int | N |  |
| `message` |  | ntext | Y |  |
| `objectVersion` |  | int | N |  |
| `refWorkItemOID` |  | nchar(32) | Y |  |

#### `MailApplication` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | char(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `id` |  | nvarchar(100) | N |  |
| `applicationDefinitionName` |  | nvarchar(100) | Y |  |
| `externalReferenceOID` |  | char(32) | Y |  |
| `isDefault` |  | int | N |  |
| `description` |  | ntext | Y |  |
| `globalApplication` |  | int | Y |  |
| `sendingTime` |  | datetime | Y |  |
| `receiverAddr` |  | ntext | N |  |
| `senderAddr` |  | nvarchar(255) | Y |  |
| `subject` |  | ntext | Y |  |
| `content` |  | ntext | Y |  |

#### `MailTask` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `taskId` |  | nchar(32) | N |  |
| `sendingTime` |  | timestamp | N |  |
| `sender` |  | nvarchar(50) | Y |  |
| `receiver` |  | nvarchar(255) | Y |  |
| `subject` |  | nvarchar(255) | Y |  |
| `content` |  | ntext | Y |  |
| `state` |  | int | N |  |

### 前綴 `dfC` — —（4 表）


#### `dfCRMBankInfo` — （無中文名）　(列數約 118)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `dpdCurrencyType` |  | nvarchar(255) | Y |  |
| `dpdForeignTransferFee` |  | nvarchar(255) | Y |  |
| `TB1` |  | nvarchar(255) | Y |  |
| `tbAccShortNm` |  | nvarchar(255) | Y |  |
| `tbBankAccNo` |  | nvarchar(255) | Y |  |
| `TB3` |  | datetime | Y |  |
| `tbAccNo` |  | nvarchar(255) | Y |  |
| `TB2` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `TB4` |  | nvarchar(255) | Y |  |
| `tbBankCode` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `htbAccId` |  | nvarchar(255) | Y |  |
| `tbAccName` |  | nvarchar(255) | Y |  |
| `tbNotifyEmail1` |  | nvarchar(255) | Y |  |
| `tbBankAccNm` |  | nvarchar(255) | Y |  |
| `tbNotifyEmail2` |  | nvarchar(255) | Y |  |
| `tbBankName` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `dpdRemittanceFee` |  | nvarchar(255) | Y |  |
| `htbSuplierCode` |  | nvarchar(255) | Y |  |
| `htbTaxNo` |  | nvarchar(255) | Y |  |
| `htbIsPosMember` |  | nvarchar(255) | Y |  |
| `htbZipCode` |  | nvarchar(255) | Y |  |
| `htbsAccountDt` |  | nvarchar(255) | Y |  |
| `htbPhone` |  | nvarchar(255) | Y |  |
| `htbChineseNm` |  | nvarchar(255) | Y |  |
| `htbAddress1` |  | nvarchar(255) | Y |  |
| `htbCountyId` |  | nvarchar(255) | Y |  |
| `htbAddress2` |  | nvarchar(255) | Y |  |
| `htbAddress3` |  | nvarchar(255) | Y |  |
| `htbFax` |  | nvarchar(255) | Y |  |
| `htbTownshipId` |  | nvarchar(255) | Y |  |
| `htbUniformCode` |  | nvarchar(255) | Y |  |
| `htbEmpCode` |  | nvarchar(255) | Y |  |
| `htbMobile` |  | nvarchar(255) | Y |  |
| `htbVipCustomer` |  | nvarchar(255) | Y |  |
| `htbAttachment` |  | nvarchar(255) | Y |  |
| `tbNote` |  | nvarchar(255) | Y |  |
| `dpdReason` |  | nvarchar(255) | Y |  |
| `tbAccId` |  | nvarchar(255) | Y |  |
| `tbNotifyEmail_hw2` |  | nvarchar(255) | Y |  |
| `tbNotifyEmail_hw1` |  | nvarchar(255) | Y |  |

#### `dfCreditEvaluate` — （無中文名）　(列數約 40)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `dfcreditevl_growth_rate` |  | float | Y |  |
| `dfcreditevl_capital` |  | nvarchar(255) | Y |  |
| `dfcreditevl_weight` |  | float | Y |  |
| `dfcreditevl_pay_condition` |  | nvarchar(255) | Y |  |
| `dfcreditevl_account` |  | nvarchar(255) | Y |  |
| `hdndfcreditevl_neighbor` |  | int | Y |  |
| `hdndfcreditevl_username` |  | nvarchar(255) | Y |  |
| `dfcreditevl_level` |  | nvarchar(255) | Y |  |
| `hdndfcreditevl_bloccode` |  | nvarchar(255) | Y |  |
| `dfcreditevl_bank_note_desc` |  | nvarchar(255) | Y |  |
| `dfcreditevl_rec_days` |  | int | Y |  |
| `dfcreditevl_aziname` |  | nvarchar(255) | Y |  |
| `hdndfcreditevl_custcode` |  | nvarchar(255) | Y |  |
| `hdndfcreditevl_azicode` |  | nvarchar(255) | Y |  |
| `dfcreditevl_peer` |  | nvarchar(255) | Y |  |
| `dfcreditevl_no` |  | nvarchar(255) | Y |  |
| `dfcreditevl_deptname` |  | nvarchar(255) | Y |  |
| `dfcreditevl_paper_credit` |  | nvarchar(255) | Y |  |
| `dfcreditevl_neighbor` |  | nvarchar(255) | Y |  |
| `hdndfcreditevl_creditstatus` |  | int | Y |  |
| `hdndfcreditevl_comptype` |  | int | Y |  |
| `dfcreditevl_paper_credit_desc` |  | nvarchar(255) | Y |  |
| `hdndfcreditevl_bosscode` |  | nvarchar(255) | Y |  |
| `dfcreditevl_custvat` |  | nvarchar(255) | Y |  |
| `dfcreditevl_score` |  | int | Y |  |
| `dfcreditevl_desc` |  | nvarchar(255) | Y |  |
| `dfcreditevl_blocname` |  | nvarchar(255) | Y |  |
| `dfcreditevl_user` |  | nvarchar(255) | Y |  |
| `dfcreditevl_custname` |  | nvarchar(255) | Y |  |
| `dfcreditevl_credit_amount_trail` |  | float | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `hdndfcreditevl_compfounded` |  | int | Y |  |
| `hdndfcreditapy_bossname` |  | nvarchar(255) | Y |  |
| `dfcreditevl_credit_amount_approved` |  | float | Y |  |
| `dfcreditevl_credit_invtg` |  | nvarchar(255) | Y |  |
| `dfcreditevl_blocvat` |  | nvarchar(255) | Y |  |
| `hdndfcreditevl_capital` |  | int | Y |  |
| `hdndfcreditevl_deptOID` |  | nvarchar(255) | Y |  |
| `dfcreditevl_creditstatus` |  | nvarchar(255) | Y |  |
| `hdndfcreditevl_fdept` |  | nvarchar(255) | Y |  |
| `hdndfcreditevl_peer` |  | int | Y |  |
| `dfcreditevl_comptype` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `dfcreditevl_turnover` |  | nvarchar(255) | Y |  |
| `hdndfcreditevl_turnover` |  | int | Y |  |
| `dfcreditevl_credit_invtg_desc` |  | nvarchar(255) | Y |  |
| `dfcreditevl_bank_note` |  | nvarchar(255) | Y |  |
| `hdndfcreditevl_deptcode` |  | nvarchar(255) | Y |  |
| `dfcreditevl_datetime` |  | datetime | Y |  |
| `dfcreditevl_rec_condition` |  | nvarchar(255) | Y |  |
| `dfcreditevl_custlist` |  | nvarchar(255) | Y |  |
| `dfcreditevl_compfounded` |  | nvarchar(255) | Y |  |
| `dfcreditevl_tran_amount` |  | float | Y |  |
| `dfcreditevl_creditdate` |  | datetime | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |

#### `dfCT` — （無中文名）　(列數約 27)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nvarchar(255) | N | PK |
| `dfct_contract` |  | nvarchar(255) | Y |  |
| `dfct_amount_est` |  | nvarchar(255) | Y |  |
| `dfct_dept` |  | nvarchar(255) | Y |  |
| `dfct_comp` |  | nvarchar(255) | Y |  |
| `Date24` |  | datetime | Y |  |
| `Date27` |  | datetime | Y |  |
| `hdndfct_typename` |  | nvarchar(255) | Y |  |
| `dfct_related` |  | nvarchar(255) | Y |  |
| `dfct_desc` |  | nvarchar(255) | Y |  |
| `hdndfct_deptname` |  | nvarchar(255) | Y |  |
| `dfct_enddate` |  | datetime | Y |  |
| `dfct_user` |  | nvarchar(255) | Y |  |
| `dfct_createtime` |  | datetime | Y |  |
| `hdndfct_amount_estname` |  | nvarchar(255) | Y |  |
| `dfct_no` |  | nvarchar(255) | Y |  |
| `dfct_file_date` |  | datetime | Y |  |
| `Date23` |  | datetime | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `dfct_type` |  | nvarchar(255) | Y |  |
| `dfct_seal_date` |  | datetime | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `dfct_first` |  | nvarchar(255) | Y |  |
| `dfct_begindate` |  | datetime | Y |  |
| `dfct_pfm_bond` |  | nvarchar(255) | Y |  |
| `hdndfct_pfm_bond_name` |  | nvarchar(255) | Y |  |
| `dfct_pfm_bond_amount` |  | int | Y |  |
| `dfct_pfm_bond_io` |  | nvarchar(255) | Y |  |
| `hdndfct_comp` |  | nvarchar(255) | Y |  |
| `hdndfct_compname` |  | nvarchar(255) | Y |  |
| `hdndfct_first` |  | nvarchar(255) | Y |  |
| `hdndfct_username` |  | nvarchar(255) | Y |  |
| `hdndfct_pfm_bond_io` |  | nvarchar(255) | Y |  |
| `hdndfct_user_deptID` |  | nvarchar(255) | Y |  |
| `hdndfct_bossID` |  | nvarchar(255) | Y |  |
| `hdndfct_user_deptOID` |  | nvarchar(255) | Y |  |

#### `dfCT_auth` — （無中文名）　(列數約 2)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nvarchar(255) | N | PK |
| `dfct_contract` |  | nvarchar(255) | Y |  |
| `dfct_user` |  | nvarchar(255) | Y |  |
| `dfct_no` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `TextBox594` |  | nvarchar(255) | Y |  |
| `TextBox435` |  | nvarchar(255) | Y |  |
| `CheckBox402` |  | nvarchar(255) | Y |  |
| `CheckBox401` |  | nvarchar(255) | Y |  |
| `CheckBox400` |  | nvarchar(255) | Y |  |
| `TextBox433` |  | nvarchar(255) | Y |  |
| `TextBox434` |  | nvarchar(255) | Y |  |
| `CheckBox276` |  | nvarchar(255) | Y |  |
| `CheckBox588` |  | nvarchar(255) | Y |  |
| `CheckBox403` |  | nvarchar(255) | Y |  |
| `CheckBox589` |  | nvarchar(255) | Y |  |
| `CheckBox581` |  | nvarchar(255) | Y |  |
| `TextBox90` |  | nvarchar(255) | Y |  |
| `CheckBox419` |  | nvarchar(255) | Y |  |
| `CheckBox390` |  | nvarchar(255) | Y |  |
| `CheckBox418` |  | nvarchar(255) | Y |  |
| `TextBox582` |  | nvarchar(255) | Y |  |
| `TextBox391` |  | nvarchar(255) | Y |  |
| `CheckBox413` |  | nvarchar(255) | Y |  |
| `CheckBox396` |  | nvarchar(255) | Y |  |
| `CheckBox393` |  | nvarchar(255) | Y |  |
| `CheckBox415` |  | nvarchar(255) | Y |  |
| `CheckBox319` |  | nvarchar(255) | Y |  |
| `CheckBox417` |  | nvarchar(255) | Y |  |
| `CheckBox597` |  | nvarchar(255) | Y |  |
| `CheckBox416` |  | nvarchar(255) | Y |  |
| `CheckBox596` |  | nvarchar(255) | Y |  |
| `CheckBox595` |  | nvarchar(255) | Y |  |
| `CheckBox593` |  | nvarchar(255) | Y |  |
| `CheckBox713` |  | nvarchar(255) | Y |  |
| `CheckBox591` |  | nvarchar(255) | Y |  |
| `CheckBox714` |  | nvarchar(255) | Y |  |
| `CheckBox590` |  | nvarchar(255) | Y |  |
| `CheckBox711` |  | nvarchar(255) | Y |  |
| `Textbox20` |  | nvarchar(255) | Y |  |
| `CheckBox715` |  | nvarchar(255) | Y |  |
| `TextBox394` |  | nvarchar(255) | Y |  |
| `CheckBox716` |  | nvarchar(255) | Y |  |
| `TextBox398` |  | nvarchar(255) | Y |  |
| `CheckBox564` |  | nvarchar(255) | Y |  |
| `TextBox106` |  | nvarchar(255) | Y |  |
| `CheckBox566` |  | nvarchar(255) | Y |  |
| `CheckBox567` |  | nvarchar(255) | Y |  |
| `CheckBox568` |  | nvarchar(255) | Y |  |
| `CheckBox423` |  | nvarchar(255) | Y |  |
| `CheckBox422` |  | nvarchar(255) | Y |  |
| `CheckBox421` |  | nvarchar(255) | Y |  |
| `CheckBox420` |  | nvarchar(255) | Y |  |
| `Checkbox21` |  | nvarchar(255) | Y |  |
| `Checkbox22` |  | nvarchar(255) | Y |  |
| `CheckBox159` |  | nvarchar(255) | Y |  |
| `CheckBox577` |  | nvarchar(255) | Y |  |
| `CheckBox436` |  | nvarchar(255) | Y |  |
| `CheckBox578` |  | nvarchar(255) | Y |  |
| `CheckBox575` |  | nvarchar(255) | Y |  |
| `CheckBox433` |  | nvarchar(255) | Y |  |
| `CheckBox432` |  | nvarchar(255) | Y |  |
| `CheckBox431` |  | nvarchar(255) | Y |  |
| `CheckBox89` |  | nvarchar(255) | Y |  |
| `CheckBox88` |  | nvarchar(255) | Y |  |
| `Checkbox15` |  | nvarchar(255) | Y |  |
| `CheckBox86` |  | nvarchar(255) | Y |  |
| `CheckBox830` |  | nvarchar(255) | Y |  |
| `CheckBox182` |  | nvarchar(255) | Y |  |
| `TextBox161` |  | nvarchar(255) | Y |  |
| `CheckBox348` |  | nvarchar(255) | Y |  |
| `CheckBox181` |  | nvarchar(255) | Y |  |
| `TextBox50` |  | nvarchar(255) | Y |  |
| `CheckBox351` |  | nvarchar(255) | Y |  |
| `TextBox152` |  | nvarchar(255) | Y |  |
| `TextBox542` |  | nvarchar(255) | Y |  |
| `TextBox350` |  | nvarchar(255) | Y |  |
| `dfct_createtime` |  | datetime | Y |  |
| `TextBox291` |  | nvarchar(255) | Y |  |
| `Checkbox30` |  | nvarchar(255) | Y |  |
| `CheckBox321` |  | nvarchar(255) | Y |  |
| `TextBox414` |  | nvarchar(255) | Y |  |
| `TextBox417` |  | nvarchar(255) | Y |  |
| `CheckBox48` |  | nvarchar(255) | Y |  |
| `CheckBox160` |  | nvarchar(255) | Y |  |
| `CheckBox162` |  | nvarchar(255) | Y |  |
| `TextBox183` |  | nvarchar(255) | Y |  |
| `CheckBox51` |  | nvarchar(255) | Y |  |
| `TextBox180` |  | nvarchar(255) | Y |  |
| `CheckBox290` |  | nvarchar(255) | Y |  |
| `CheckBox664` |  | nvarchar(255) | Y |  |
| `TextBox423` |  | nvarchar(255) | Y |  |
| `TextBox421` |  | nvarchar(255) | Y |  |
| `TextBox420` |  | nvarchar(255) | Y |  |
| `CheckBox105` |  | nvarchar(255) | Y |  |
| `CheckBox283` |  | nvarchar(255) | Y |  |
| `TextBox320` |  | nvarchar(255) | Y |  |
| `CheckBox107` |  | nvarchar(255) | Y |  |

### 前綴 `Gro` — —（2 表）


#### `Group_User` — （無中文名）　(列數約 85)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `GroupOID` |  | nchar(32) | N | PK |
| `UserOID` |  | nchar(32) | N | PK |

#### `Groups` — （無中文名）　(列數約 55)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `id` |  | nvarchar(100) | N |  |
| `groupName` |  | nvarchar(100) | N |  |
| `organizationOID` |  | nchar(32) | N |  |
| `description` |  | ntext | Y |  |

### 前綴 `Aut` — —（6 表）


#### `AuthorityRight` — （無中文名）　(列數約 42)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `targetType` |  | int | N |  |
| `rightName` |  | nvarchar(255) | N |  |
| `containerOID` |  | nchar(32) | Y |  |
| `levelValue` |  | int | N |  |
| `linkURL` |  | nvarchar(1000) | Y |  |
| `authorizedTargetsString` |  | ntext | Y |  |

#### `AuthorityGroup` — （無中文名）　(列數約 21)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `groupId` |  | nvarchar(100) | N |  |
| `groupName` |  | nvarchar(255) | Y |  |
| `authorityUnitsOID` |  | nchar(32) | N |  |
| `validFrom` |  | datetime | Y |  |
| `validTo` |  | datetime | Y |  |

#### `AuthorityScopeSlot` — （無中文名）　(列數約 21)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `slotNumber` |  | int | N |  |
| `ownerOID` |  | nchar(32) | N |  |
| `includeSubUnits` |  | int | N |  |
| `containerOID` |  | nchar(32) | Y |  |
| `scopeOID` |  | nchar(32) | N |  |

#### `AuthorityUnits` — （無中文名）　(列數約 21)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `unitId` |  | nvarchar(100) | N |  |
| `unitName` |  | nvarchar(255) | Y |  |
| `groupList` |  | ntext | Y |  |
| `organizationUnitList` |  | ntext | Y |  |
| `functionDefList` |  | ntext | Y |  |
| `userList` |  | ntext | Y |  |

#### `AuthorityScope` — （無中文名）　(列數約 2)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `scopeId` |  | nvarchar(100) | N |  |
| `scopeName` |  | nvarchar(255) | Y |  |
| `scopeType` |  | nvarchar(100) | N |  |
| `priorityLevel` |  | int | N |  |
| `bundleContainer` |  | ntext | Y |  |

#### `AutoAgent` — （無中文名）　(列數約 1)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `id` |  | nvarchar(100) | N |  |
| `objectVersion` |  | int | N |  |
| `autoAgentName` |  | nvarchar(100) | N |  |

### 前綴 `dfr` — —（1 表）


#### `dfrequest` — （無中文名）　(列數約 107)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `dfreq_deptname` |  | nvarchar(255) | Y |  |
| `dfreq_deptcode` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `dfreq_appdate` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `dfreq_finaldate` |  | datetime | Y |  |
| `dfreq_type` |  | nvarchar(255) | Y |  |
| `dfreq_usercode` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `dfreq_title` |  | nvarchar(255) | Y |  |
| `dfreq_desc` |  | nvarchar(255) | Y |  |
| `dfreq_hdn_username` |  | nvarchar(255) | Y |  |
| `dfreq_hdn_boss` |  | nvarchar(255) | Y |  |
| `dfreq_no` |  | nvarchar(255) | Y |  |
| `dfreq_hdn_edesc` |  | nvarchar(255) | Y |  |
| `dfreq_hdn_deptOID` |  | nvarchar(255) | Y |  |
| `hdndfreq_typename` |  | nvarchar(255) | Y |  |

### 前綴 `Att` — 附件(Attachment)（4 表）


#### `AttachmentAuthority` — （無中文名）　(列數約 71)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `allowDelete` |  | int | N |  |
| `allowUpdate` |  | int | N |  |
| `activityDefinitionOID` |  | nchar(32) | Y |  |
| `containerOID` |  | nchar(32) | N |  |
| `objectVersion` |  | int | N |  |

#### `AttachmentDefinition` — （無中文名）　(列數約 17)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `fileType` |  | nvarchar(20) | Y |  |
| `attachmentDefinitionId` |  | nvarchar(50) | N |  |
| `attachmentDefinitionName` |  | nvarchar(100) | N |  |
| `description` |  | ntext | Y |  |
| `objectVersion` |  | int | N |  |

#### `AttachmentType` — （無中文名）　(列數約 12)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `attachmentDefinitionOID` |  | nchar(32) | Y |  |

#### `AttachmentInstance` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `definitionOID` |  | nchar(32) | N |  |
| `objectVersion` |  | int | N |  |
| `docCmItemOID` |  | nchar(32) | N |  |

### 前綴 `dff` — —（2 表）


#### `dffailproduct_detail` — （無中文名）　(列數約 64)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `gd_DT4` |  | nvarchar(255) | Y |  |
| `gd_DP1` |  | nvarchar(255) | Y |  |
| `gd_DT5` |  | nvarchar(255) | Y |  |
| `gd_DT6` |  | nvarchar(255) | Y |  |
| `gd_TB10` |  | nvarchar(255) | Y |  |
| `gd_TB11` |  | nvarchar(255) | Y |  |
| `gd_TB12` |  | nvarchar(255) | Y |  |
| `gd_no` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `gd_TB9` |  | nvarchar(255) | Y |  |
| `gd_TA5` |  | nvarchar(255) | Y |  |

#### `dffailproduct` — （無中文名）　(列數約 27)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `RB1` |  | nvarchar(255) | Y |  |
| `TB1` |  | nvarchar(255) | Y |  |
| `TB3` |  | nvarchar(255) | Y |  |
| `TB2` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `TB5` |  | int | Y |  |
| `TB4` |  | nvarchar(255) | Y |  |
| `TB7` |  | int | Y |  |
| `TB6` |  | nvarchar(255) | Y |  |
| `TB8` |  | int | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `DT1` |  | datetime | Y |  |
| `DT3` |  | datetime | Y |  |
| `DT2` |  | datetime | Y |  |
| `DP1` |  | nvarchar(255) | Y |  |
| `DT5` |  | datetime | Y |  |
| `HT1` |  | int | Y |  |
| `TA2` |  | nvarchar(255) | Y |  |
| `DT4` |  | datetime | Y |  |
| `TA1` |  | nvarchar(255) | Y |  |
| `HT3` |  | nvarchar(255) | Y |  |
| `DT6` |  | datetime | Y |  |
| `HT2` |  | nvarchar(255) | Y |  |
| `TB12` |  | nvarchar(255) | Y |  |
| `HT4` |  | nvarchar(255) | Y |  |
| `TB11` |  | int | Y |  |
| `TB10` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `CH1` |  | nvarchar(255) | Y |  |
| `CH3` |  | nvarchar(255) | Y |  |
| `SN1` |  | nvarchar(255) | Y |  |
| `TB9` |  | int | Y |  |
| `DT7` |  | datetime | Y |  |
| `HT5` |  | nvarchar(255) | Y |  |
| `TA4` |  | nvarchar(255) | Y |  |
| `TA3` |  | nvarchar(255) | Y |  |
| `TA5` |  | nvarchar(255) | Y |  |
| `HT6` |  | nvarchar(255) | Y |  |
| `TA6` |  | nvarchar(255) | Y |  |

### 前綴 `Phr` — —（1 表）


#### `Phrase` — （無中文名）　(列數約 71)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `content` |  | nvarchar(100) | N |  |
| `ownerOID` |  | nchar(32) | N |  |
| `phraseType` |  | int | N |  |
| `updateTime` |  | datetime | N |  |

### 前綴 `Mcl` — —（1 表）


#### `McloudMappingKey` — （無中文名）　(列數約 55)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | char(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `definitionOID` |  | char(32) | N |  |

### 前綴 `dfc` — 自訂(df)（10 表）


#### `dfcontact` — （無中文名）　(列數約 16)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `dfcont_desc` |  | nvarchar(255) | Y |  |
| `dfcont_title` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `dfcont_sec` |  | nvarchar(255) | Y |  |
| `dfcont_date` |  | datetime | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `dfcont_usercode` |  | nvarchar(255) | Y |  |
| `dfcont_hdn_username` |  | nvarchar(255) | Y |  |
| `dfcont_hdn_deptcode` |  | nvarchar(255) | Y |  |
| `dfcont_deptname` |  | nvarchar(255) | Y |  |

#### `dfcomplaint_39` — （無中文名）　(列數約 7)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `TB3` |  | nvarchar(255) | Y |  |
| `TB2` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `TB5` |  | nvarchar(255) | Y |  |
| `TB4` |  | nvarchar(255) | Y |  |
| `TB7` |  | nvarchar(255) | Y |  |
| `TB6` |  | nvarchar(255) | Y |  |
| `TB9` |  | nvarchar(255) | Y |  |
| `TB8` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `DT1` |  | datetime | Y |  |
| `DT3` |  | datetime | Y |  |
| `DT2` |  | datetime | Y |  |
| `DP1` |  | nvarchar(255) | Y |  |
| `DT5` |  | datetime | Y |  |
| `HT1` |  | nvarchar(255) | Y |  |
| `DT4` |  | datetime | Y |  |
| `DP3` |  | nvarchar(255) | Y |  |
| `DT7` |  | datetime | Y |  |
| `DP2` |  | nvarchar(255) | Y |  |
| `DT6` |  | datetime | Y |  |
| `HT2` |  | nvarchar(255) | Y |  |
| `DP5` |  | nvarchar(255) | Y |  |
| `TB12` |  | nvarchar(255) | Y |  |
| `DP4` |  | nvarchar(255) | Y |  |
| `TB11` |  | nvarchar(255) | Y |  |
| `TB10` |  | nvarchar(255) | Y |  |
| `DP6` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `CH1` |  | nvarchar(255) | Y |  |
| `TB16` |  | nvarchar(255) | Y |  |
| `TB15` |  | nvarchar(255) | Y |  |
| `TB14` |  | nvarchar(255) | Y |  |
| `TB13` |  | nvarchar(255) | Y |  |
| `S1` |  | nvarchar(255) | Y |  |

#### `dfcnexception` — （無中文名）　(列數約 4)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `DT1` |  | datetime | Y |  |
| `RB1` |  | nvarchar(255) | Y |  |
| `RB3` |  | nvarchar(255) | Y |  |
| `TB1` |  | nvarchar(255) | Y |  |
| `RB2` |  | nvarchar(255) | Y |  |
| `HT1` |  | nvarchar(255) | Y |  |
| `TA2` |  | nvarchar(255) | Y |  |
| `TB3` |  | nvarchar(255) | Y |  |
| `RB4` |  | nvarchar(255) | Y |  |
| `TA1` |  | nvarchar(255) | Y |  |
| `TB2` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `TA4` |  | nvarchar(255) | Y |  |
| `TB5` |  | nvarchar(255) | Y |  |
| `TA3` |  | nvarchar(255) | Y |  |
| `TB4` |  | nvarchar(255) | Y |  |
| `TB7` |  | nvarchar(255) | Y |  |
| `TA5` |  | nvarchar(255) | Y |  |
| `TB6` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `SN` |  | nvarchar(255) | Y |  |

#### `dfcomplaint_43` — （無中文名）　(列數約 4)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `TB3` |  | nvarchar(255) | Y |  |
| `TB2` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `TB5` |  | nvarchar(255) | Y |  |
| `TB7` |  | nvarchar(255) | Y |  |
| `TB6` |  | nvarchar(255) | Y |  |
| `TB9` |  | nvarchar(255) | Y |  |
| `TB8` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `DT1` |  | datetime | Y |  |
| `DT3` |  | datetime | Y |  |
| `DT2` |  | datetime | Y |  |
| `DP1` |  | nvarchar(255) | Y |  |
| `DT5` |  | datetime | Y |  |
| `HT1` |  | nvarchar(255) | Y |  |
| `DT4` |  | datetime | Y |  |
| `DP3` |  | nvarchar(255) | Y |  |
| `DT7` |  | datetime | Y |  |
| `DP2` |  | nvarchar(255) | Y |  |
| `DT6` |  | datetime | Y |  |
| `HT2` |  | nvarchar(255) | Y |  |
| `DP5` |  | nvarchar(255) | Y |  |
| `TB12` |  | nvarchar(255) | Y |  |
| `DP4` |  | nvarchar(255) | Y |  |
| `TB11` |  | nvarchar(255) | Y |  |
| `DP7` |  | nvarchar(255) | Y |  |
| `TB10` |  | nvarchar(255) | Y |  |
| `DP6` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `CH1` |  | nvarchar(255) | Y |  |
| `TB16` |  | nvarchar(255) | Y |  |
| `TB15` |  | nvarchar(255) | Y |  |
| `TB14` |  | nvarchar(255) | Y |  |
| `TB13` |  | nvarchar(255) | Y |  |
| `S1` |  | nvarchar(255) | Y |  |

#### `dfcustapp` — （無中文名）　(列數約 3)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `dfcustapp_hdn_deptcode` |  | nvarchar(255) | Y |  |
| `dfcustapp_shortname` |  | nvarchar(255) | Y |  |
| `dfcustapp_deptname` |  | nvarchar(255) | Y |  |
| `dfcustapp_fax` |  | nvarchar(255) | Y |  |
| `dfcustapp_craft` |  | nvarchar(255) | Y |  |
| `dfcustapp_conemail` |  | nvarchar(255) | Y |  |
| `dfcustapp_boss` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `dfcustapp_industry` |  | nvarchar(255) | Y |  |
| `dfcustapp_type` |  | nvarchar(255) | Y |  |
| `dfcustapp_capital` |  | nvarchar(255) | Y |  |
| `dfcustapp_tel` |  | nvarchar(255) | Y |  |
| `dfcustapp_appdate` |  | nvarchar(255) | Y |  |
| `dfcustapp_level` |  | nvarchar(255) | Y |  |
| `dfcustapp_confax` |  | nvarchar(255) | Y |  |
| `Dropdown56` |  | nvarchar(255) | Y |  |
| `dfcustapp_unify` |  | nvarchar(255) | Y |  |
| `dfcustapp_custname` |  | nvarchar(255) | Y |  |
| `dfcustapp_contel` |  | nvarchar(255) | Y |  |
| `dfcustapp_conuname` |  | nvarchar(255) | Y |  |
| `dfcustapp_mobile` |  | nvarchar(255) | Y |  |
| `dfcustapp_hdn_username` |  | nvarchar(255) | Y |  |
| `dfcustapp_usercode` |  | nvarchar(255) | Y |  |
| `dfcustapp_property` |  | nvarchar(255) | Y |  |
| `dfcustapp_ship` |  | nvarchar(255) | Y |  |
| `dfcustapp_address` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `dfcustapp_sitecode` |  | nvarchar(255) | Y |  |
| `dfcustapp_emp` |  | nvarchar(255) | Y |  |

#### `dfcomplaint_42` — （無中文名）　(列數約 2)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `TB3` |  | nvarchar(255) | Y |  |
| `TB2` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `TB5` |  | nvarchar(255) | Y |  |
| `TB7` |  | nvarchar(255) | Y |  |
| `TB6` |  | nvarchar(255) | Y |  |
| `TB9` |  | nvarchar(255) | Y |  |
| `TB8` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `DT1` |  | datetime | Y |  |
| `DT3` |  | datetime | Y |  |
| `DT2` |  | datetime | Y |  |
| `DP1` |  | nvarchar(255) | Y |  |
| `DT5` |  | datetime | Y |  |
| `HT1` |  | nvarchar(255) | Y |  |
| `DT4` |  | datetime | Y |  |
| `DP3` |  | nvarchar(255) | Y |  |
| `DT7` |  | datetime | Y |  |
| `DP2` |  | nvarchar(255) | Y |  |
| `DT6` |  | datetime | Y |  |
| `HT2` |  | nvarchar(255) | Y |  |
| `DP5` |  | nvarchar(255) | Y |  |
| `TB12` |  | nvarchar(255) | Y |  |
| `DP4` |  | nvarchar(255) | Y |  |
| `TB11` |  | nvarchar(255) | Y |  |
| `DP7` |  | nvarchar(255) | Y |  |
| `TB10` |  | nvarchar(255) | Y |  |
| `DP6` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `CH1` |  | nvarchar(255) | Y |  |
| `TB16` |  | nvarchar(255) | Y |  |
| `TB15` |  | nvarchar(255) | Y |  |
| `TB14` |  | nvarchar(255) | Y |  |
| `TB13` |  | nvarchar(255) | Y |  |
| `S1` |  | nvarchar(255) | Y |  |
| `TB4` |  | nvarchar(255) | Y |  |

#### `dfcreditapply` — （無中文名）　(列數約 2)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `dfcreditapy_azicode` |  | nvarchar(255) | Y |  |
| `hdndfcreditapy_blocname` |  | nvarchar(255) | Y |  |
| `hdndfcreditapy_aziname` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `hdndfcreditapy_bossname` |  | nvarchar(255) | Y |  |
| `dfcreditapy_usercode` |  | nvarchar(255) | Y |  |
| `dfcreditapy_apymoney` |  | float | Y |  |
| `hdndfcreditapy_deptname` |  | nvarchar(255) | Y |  |
| `dfcreditapy_bloccode` |  | nvarchar(255) | Y |  |
| `dfcreditapy_apydatetime` |  | nvarchar(255) | Y |  |
| `dfcreditapy_custcode` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `hdndfcreditapy_deptOID` |  | nvarchar(255) | Y |  |
| `dfcreditapy_no` |  | nvarchar(255) | Y |  |
| `dfcreditapy_fraction` |  | float | Y |  |
| `dfcreditapy_desc` |  | nvarchar(255) | Y |  |
| `dfcreditapy_addmoney` |  | float | Y |  |
| `hdndfcreditapy_bosscode` |  | nvarchar(255) | Y |  |
| `hdndfcreditapy_username` |  | nvarchar(255) | Y |  |
| `dfcreditapy_finmoney` |  | float | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `hdndfcreditapy_custname` |  | nvarchar(255) | Y |  |
| `dfcreditapy_deptcode` |  | nvarchar(255) | Y |  |

#### `dfchecklist_7` — （無中文名）　(列數約 1)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `DT1` |  | datetime | Y |  |
| `RB1` |  | nvarchar(255) | Y |  |
| `CB2` |  | nvarchar(255) | Y |  |
| `TB1` |  | nvarchar(255) | Y |  |
| `DT2` |  | datetime | Y |  |
| `CB4` |  | nvarchar(255) | Y |  |
| `CB3` |  | nvarchar(255) | Y |  |
| `TB2` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |

#### `dfchrequest` — （無中文名）　(列數約 1)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `RB1` |  | nvarchar(255) | Y |  |
| `RB3` |  | nvarchar(255) | Y |  |
| `TB1` |  | nvarchar(255) | Y |  |
| `RB2` |  | nvarchar(255) | Y |  |
| `RB5` |  | nvarchar(255) | Y |  |
| `TB3` |  | nvarchar(255) | Y |  |
| `RB4` |  | nvarchar(255) | Y |  |
| `TB2` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `RB7` |  | nvarchar(255) | Y |  |
| `TB5` |  | nvarchar(255) | Y |  |
| `RB6` |  | nvarchar(255) | Y |  |
| `TB4` |  | nvarchar(255) | Y |  |
| `RB9` |  | nvarchar(255) | Y |  |
| `TB7` |  | nvarchar(255) | Y |  |
| `RB8` |  | nvarchar(255) | Y |  |
| `TB6` |  | nvarchar(255) | Y |  |
| `TB9` |  | nvarchar(255) | Y |  |
| `TB8` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `DT1` |  | datetime | Y |  |
| `HT1` |  | nvarchar(255) | Y |  |
| `TA2` |  | nvarchar(255) | Y |  |
| `TA1` |  | nvarchar(255) | Y |  |
| `HT3` |  | nvarchar(255) | Y |  |
| `HT2` |  | nvarchar(255) | Y |  |
| `TA3` |  | nvarchar(255) | Y |  |
| `RB10` |  | nvarchar(255) | Y |  |
| `TB10` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |

#### `dfcomplaint` — （無中文名）　(列數約 1)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `TB3` |  | nvarchar(255) | Y |  |
| `TB2` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `TB5` |  | nvarchar(255) | Y |  |
| `TB4` |  | nvarchar(255) | Y |  |
| `TB7` |  | nvarchar(255) | Y |  |
| `TB6` |  | nvarchar(255) | Y |  |
| `TB9` |  | nvarchar(255) | Y |  |
| `TB8` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `DT1` |  | datetime | Y |  |
| `DT3` |  | datetime | Y |  |
| `DT2` |  | datetime | Y |  |
| `DP1` |  | nvarchar(255) | Y |  |
| `DT5` |  | datetime | Y |  |
| `HT1` |  | nvarchar(255) | Y |  |
| `DT4` |  | datetime | Y |  |
| `DP3` |  | nvarchar(255) | Y |  |
| `DT7` |  | datetime | Y |  |
| `DP2` |  | nvarchar(255) | Y |  |
| `DT6` |  | datetime | Y |  |
| `HT2` |  | nvarchar(255) | Y |  |
| `DP5` |  | nvarchar(255) | Y |  |
| `TB12` |  | nvarchar(255) | Y |  |
| `DP4` |  | nvarchar(255) | Y |  |
| `TB11` |  | nvarchar(255) | Y |  |
| `TB10` |  | nvarchar(255) | Y |  |
| `DP6` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `CH1` |  | nvarchar(255) | Y |  |
| `TB16` |  | nvarchar(255) | Y |  |
| `TB15` |  | nvarchar(255) | Y |  |
| `TB14` |  | nvarchar(255) | Y |  |
| `TB13` |  | nvarchar(255) | Y |  |
| `S1` |  | nvarchar(255) | Y |  |

### 前綴 `Web` — —（2 表）


#### `WebApplication` — （無中文名）　(列數約 27)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | char(32) | N | PK |
| `objectVersion` |  | int | Y |  |
| `id` |  | nvarchar(100) | N |  |
| `applicationDefinitionName` |  | nvarchar(100) | Y |  |
| `externalReferenceOID` |  | char(32) | Y |  |
| `isDefault` |  | int | N |  |
| `description` |  | ntext | Y |  |
| `allowUserInteraction` |  | int | Y |  |
| `requestMethod` |  | nvarchar(50) | Y |  |
| `urlString` |  | nvarchar(255) | N |  |
| `usingProxy` |  | int | Y |  |
| `usingSSL` |  | int | Y |  |
| `successCodes` |  | nvarchar(255) | Y |  |
| `globalApplication` |  | int | Y |  |
| `autoApproval` |  | int | N |  |

#### `WebServicesApplication` — （無中文名）　(列數約 3)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | char(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `id` |  | nvarchar(100) | N |  |
| `applicationDefinitionName` |  | nvarchar(100) | N |  |
| `externalReferenceOID` |  | char(32) | Y |  |
| `isDefault` |  | int | N |  |
| `description` |  | ntext | Y |  |
| `wsdlURL` |  | nvarchar(255) | N |  |
| `portName` |  | nvarchar(255) | Y |  |
| `operationName` |  | nvarchar(255) | N |  |
| `globalApplication` |  | int | Y |  |

### 前綴 `Arc` — —（7 表）


#### `ArchiveProperties` — （無中文名）　(列數約 15)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `paraKey` |  | nvarchar(256) | Y |  |
| `paraValue` |  | nvarchar(256) | Y |  |
| `description` |  | ntext | Y |  |

#### `ArchiveEventRecord` — （無中文名）　(列數約 7)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `eventLevel` |  | nvarchar(16) | Y |  |
| `dateTime` |  | datetime | Y |  |
| `userId` |  | nvarchar(100) | Y |  |
| `sourceIp` |  | nvarchar(100) | Y |  |
| `actionType` |  | nchar(1) | Y |  |
| `description` |  | ntext | Y |  |
| `successProccessNum` |  | int | Y |  |
| `failProcessNum` |  | int | Y |  |
| `processRuleOID` |  | nchar(32) | Y |  |

#### `ArchiveProcessDetail` — （無中文名）　(列數約 7)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `processOID` |  | nchar(32) | Y |  |
| `processSubject` |  | ntext | Y |  |
| `processInstanceName` |  | nvarchar(255) | Y |  |
| `serialNumber` |  | nvarchar(100) | Y |  |
| `dateTime` |  | datetime | Y |  |
| `actionType` |  | nchar(1) | Y |  |
| `actionResult` |  | nchar(1) | Y |  |
| `description` |  | ntext | Y |  |
| `archiveEventOID` |  | nchar(32) | Y |  |

#### `ArchiveExcludedProcess` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `processCategoryOID` |  | nchar(32) | Y |  |
| `ownerOID` |  | nchar(32) | Y |  |
| `ownerId` |  | nvarchar(100) | Y |  |
| `ownerName` |  | nvarchar(100) | Y |  |
| `processId` |  | nvarchar(100) | Y |  |

#### `ArchiveProcessInReduction` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `processOID` |  | nchar(32) | Y |  |
| `userOID` |  | nchar(32) | Y |  |
| `executeType` |  | nchar(1) | Y |  |
| `archiveEventOID` |  | nchar(32) | Y |  |

#### `ArchiveProcessRule` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `name` |  | nvarchar(100) | Y |  |
| `processCategoryOID` |  | nchar(32) | Y |  |
| `processIds` |  | ntext | Y |  |
| `completeType` |  | char(1) | Y |  |
| `overTime` |  | int | Y |  |
| `overTimeUnit` |  | nvarchar(50) | Y |  |
| `ownerOID` |  | nchar(32) | Y |  |
| `ownerId` |  | nvarchar(100) | Y |  |
| `ownerName` |  | nvarchar(100) | Y |  |

#### `ArchiveTimeSchedule` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `mainIsEnable` |  | nvarchar(10) | Y |  |
| `week` |  | int | Y |  |
| `isEnable` |  | nvarchar(10) | Y |  |
| `executionInterval` |  | ntext | Y |  |
| `jobName` |  | nvarchar(64) | Y |  |
| `jobGroupName` |  | nvarchar(64) | Y |  |
| `triggerName` |  | nvarchar(64) | Y |  |
| `triggerGroupName` |  | nvarchar(64) | Y |  |

### 前綴 `Mod` — —（1 表）


#### `ModuleDefinition` — （無中文名）　(列數約 27)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `id` |  | nvarchar(50) | N |  |
| `name` |  | nvarchar(100) | N |  |
| `isDefault` |  | int | N |  |
| `bundleContainer` |  | ntext | Y |  |
| `containerOID` |  | nchar(32) | Y |  |
| `updateTime` |  | datetime | N |  |
| `updaterOID` |  | nchar(32) | N |  |
| `icon` |  | nvarchar(256) | Y |  |

### 前綴 `Per` — 權限/人員（6 表）


#### `PerDataPro` — （無中文名）　(列數約 16)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | Y |  |
| `bundleContainer` |  | ntext | Y |  |
| `id` |  | nvarchar(100) | N |  |
| `perDataProName` |  | nvarchar(500) | N |  |
| `typeId` |  | nvarchar(100) | N |  |
| `maskSymbol` |  | nvarchar(10) | N |  |
| `maskStartingPos` |  | nvarchar(10) | Y |  |
| `maskEndPos` |  | nvarchar(10) | Y |  |
| `maskNum` |  | int | Y |  |
| `isDefault` |  | int | Y |  |
| `modifiedUserOID` |  | nchar(32) | N |  |
| `modifiedTime` |  | datetime | N |  |

#### `PerDataProType` — （無中文名）　(列數約 7)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | Y |  |
| `bundleContainer` |  | ntext | Y |  |
| `id` |  | nvarchar(100) | N |  |
| `typeDescription` |  | nvarchar(500) | N |  |

#### `PersonalizeExcludeUsers` — （無中文名）　(列數約 1)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `userOID` |  | nchar(32) | N | PK |

#### `PercentagePerPerson` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `containerOID` |  | nchar(32) | Y |  |
| `percentage` |  | int | N |  |
| `employeeId` |  | nvarchar(100) | N |  |
| `organizationId` |  | nvarchar(100) | N |  |

#### `PerformanceData` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `startTime` |  | datetime | N |  |
| `endTime` |  | datetime | N |  |
| `executeDetail` |  | nvarchar(100) | N |  |
| `containerOID` |  | nchar(32) | N |  |
| `executionTime` |  | bigint | N |  |
| `formInstanceOID` |  | nchar(32) | Y |  |
| `formSerialNumber` |  | nvarchar(100) | Y |  |
| `fromId` |  | nvarchar(100) | Y |  |

#### `PerformanceRecord` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `operatorOID` |  | nvarchar(100) | N |  |
| `executedTime` |  | datetime | N |  |
| `operationTiming` |  | nvarchar(100) | N |  |
| `processInstanceOID` |  | nchar(32) | Y |  |
| `processSerialNumber` |  | nvarchar(100) | Y |  |
| `processId` |  | nvarchar(100) | Y |  |
| `detailDesc` |  | nvarchar(100) | N |  |

### 前綴 `Sql` — —（2 表）


#### `SqlAllowedForm` — （無中文名）　(列數約 21)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `formId` |  | nvarchar(256) | N |  |
| `containerOID` |  | nvarchar(32) | N |  |

#### `SqlAllowedJsp` — （無中文名）　(列數約 3)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `jspId` |  | nvarchar(256) | N |  |
| `containerOID` |  | nvarchar(32) | N |  |

### 前綴 `tes` — —（7 表）


#### `testdfsuggest` — （無中文名）　(列數約 8)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `hdndfsug_secertname` |  | nvarchar(255) | Y |  |
| `hdndfsug_kindname` |  | nvarchar(255) | Y |  |
| `dfsug_desc` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `dfsug_secert` |  | nvarchar(255) | Y |  |
| `dfsug_user` |  | nvarchar(255) | Y |  |
| `dfsug_no` |  | nvarchar(255) | Y |  |
| `dfsug_advise` |  | nvarchar(255) | Y |  |
| `dfsug_hdn_username` |  | nvarchar(255) | Y |  |
| `dfsug_hdn_edesc` |  | nvarchar(255) | Y |  |
| `dfsug_title` |  | nvarchar(255) | Y |  |
| `dfsug_sdate` |  | datetime | Y |  |
| `dfsug_hdn_deptcode` |  | nvarchar(255) | Y |  |
| `dfsug_kind` |  | nvarchar(255) | Y |  |
| `dfsug_deptname` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |

#### `testdfexpense_detail` — （無中文名）　(列數約 6)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `dfexp_gdtraffic` |  | nvarchar(255) | Y |  |
| `dfexp_gdmeal` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `dfexp_gdsplace` |  | nvarchar(255) | Y |  |
| `dfexp_gdemile` |  | nvarchar(255) | Y |  |
| `dfexp_gdothitem` |  | nvarchar(255) | Y |  |
| `dfexp_gddate` |  | nvarchar(255) | Y |  |
| `dfexp_hdn_gdtype` |  | nvarchar(255) | Y |  |
| `dfexp_gdtype` |  | nvarchar(255) | Y |  |
| `dfexp_gdfood` |  | nvarchar(255) | Y |  |
| `dfsug_gddesc` |  | nvarchar(255) | Y |  |
| `dfexp_gdsum` |  | nvarchar(255) | Y |  |
| `dfexp_gdothfee` |  | nvarchar(255) | Y |  |
| `dfexp_gdno` |  | nvarchar(255) | Y |  |
| `dfexp_gdmix` |  | nvarchar(255) | Y |  |
| `dfexp_gdeplace` |  | nvarchar(255) | Y |  |
| `dfexp_gdsmile` |  | nvarchar(255) | Y |  |
| `dfexp_hdn_gdtoolname` |  | nvarchar(255) | Y |  |
| `dfexp_gdmile` |  | nvarchar(255) | Y |  |
| `dfexp_gdhotel` |  | nvarchar(255) | Y |  |
| `dfexp_gdtool` |  | nvarchar(255) | Y |  |
| `dfexp_gdsocial` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |

#### `testdfexpense` — （無中文名）　(列數約 3)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nvarchar(255) | N | PK |
| `dfexp_tool` |  | nvarchar(255) | Y |  |
| `dfexp_hdn_toolname` |  | nvarchar(255) | Y |  |
| `dfexp_date` |  | datetime | Y |  |
| `dfexp_sum` |  | float | Y |  |
| `dfexp_hdn_username` |  | nvarchar(255) | Y |  |
| `dfexp_smile` |  | float | Y |  |
| `dfexp_traffic` |  | float | Y |  |
| `dfexp_meal` |  | float | Y |  |
| `dfexp_splace` |  | nvarchar(255) | Y |  |
| `dfexp_hdn_atype` |  | nvarchar(255) | Y |  |
| `dfexp_pay` |  | float | Y |  |
| `dfexp_hdn_boss` |  | nvarchar(255) | Y |  |
| `dfexp_hdn_deptcode` |  | nvarchar(255) | Y |  |
| `dfexp_hdn_deptOID` |  | nvarchar(255) | Y |  |
| `dfexp_hdn_type` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `dfsug_desc` |  | nvarchar(255) | Y |  |
| `dfexp_emile` |  | float | Y |  |
| `dfexp_hdn_asplace` |  | nvarchar(255) | Y |  |
| `dfexp_social` |  | float | Y |  |
| `dfexp_food` |  | float | Y |  |
| `dfexp_othitem` |  | nvarchar(255) | Y |  |
| `dfexp_othfee` |  | float | Y |  |
| `dfexp_prepay` |  | float | Y |  |
| `dfexp_mix` |  | float | Y |  |
| `dfexp_hdn_fdept` |  | nvarchar(255) | Y |  |
| `dfexp_hotel` |  | float | Y |  |
| `dfexp_deptname` |  | nvarchar(255) | Y |  |
| `dfexp_user` |  | nvarchar(255) | Y |  |
| `dfexp_hdn_atool` |  | nvarchar(255) | Y |  |
| `dfexp_type` |  | nvarchar(255) | Y |  |
| `dfexp_total` |  | float | Y |  |
| `dfexp_mile` |  | float | Y |  |
| `dfexp_hdn_aeplace` |  | nvarchar(255) | Y |  |
| `dfexp_eplace` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `dfexp_hdn_adate` |  | nvarchar(255) | Y |  |
| `dfexp_no` |  | nvarchar(255) | Y |  |
| `dfexp_apdate` |  | nvarchar(255) | Y |  |

#### `testdfgovernment` — （無中文名）　(列數約 3)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `hdndfcont_secname` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `dfcont_hdn_edesc` |  | nvarchar(255) | Y |  |
| `dfcont_hdn_deptcode` |  | nvarchar(255) | Y |  |
| `dfcont_no` |  | nvarchar(255) | Y |  |
| `dfcont_date` |  | datetime | Y |  |
| `dfcont_usercode` |  | nvarchar(255) | Y |  |
| `dfcont_deptname` |  | nvarchar(255) | Y |  |
| `dfcont_sec` |  | nvarchar(255) | Y |  |
| `dfcont_hdn_username` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `dfcont_hdn_deptOID` |  | nvarchar(255) | Y |  |
| `dfcont_title` |  | nvarchar(255) | Y |  |
| `dfcont_hdn_boss` |  | nvarchar(255) | Y |  |
| `dfcont_desc` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |

#### `testdfpurchase_detail` — （無中文名）　(列數約 2)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nvarchar(255) | N | PK |
| `dfpur_gdprice` |  | nvarchar(255) | Y |  |
| `dfpur_gdunit` |  | nvarchar(255) | Y |  |
| `dfpur_gdsum` |  | nvarchar(255) | Y |  |
| `dfpur_gditem` |  | nvarchar(255) | Y |  |
| `dfpur_gdno` |  | nvarchar(255) | Y |  |
| `dfpur_gdcount` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |

#### `testdfpurchase` — （無中文名）　(列數約 1)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nvarchar(255) | N | PK |
| `dfpur_appdate` |  | nvarchar(255) | Y |  |
| `dfpur_hdn_username` |  | nvarchar(255) | Y |  |
| `dfpur_count` |  | float | Y |  |
| `dfpur_desc` |  | nvarchar(255) | Y |  |
| `hdndfpur_typename` |  | nvarchar(255) | Y |  |
| `dfpur_hdn_fdept` |  | nvarchar(255) | Y |  |
| `hdndfpur_appkindname` |  | nvarchar(255) | Y |  |
| `dfpur_tax` |  | float | Y |  |
| `dfpur_chktax` |  | nvarchar(255) | Y |  |
| `dfpur_type` |  | nvarchar(255) | Y |  |
| `dfpur_unit` |  | nvarchar(255) | Y |  |
| `dfpur_supplier` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `dfpur_hdn_deptOID` |  | nvarchar(255) | Y |  |
| `dfpur_place` |  | nvarchar(255) | Y |  |
| `dfpur_no` |  | nvarchar(255) | Y |  |
| `dfpur_item` |  | nvarchar(255) | Y |  |
| `dfpur_hdn_boss` |  | nvarchar(255) | Y |  |
| `dfpur_refer` |  | nvarchar(255) | Y |  |
| `dfpur_user` |  | nvarchar(255) | Y |  |
| `dfpur_price` |  | float | Y |  |
| `dfpur_reqdate` |  | datetime | Y |  |
| `dfpur_deptname` |  | nvarchar(255) | Y |  |
| `dfpur_convey` |  | nvarchar(255) | Y |  |
| `dfpur_hdn_edesc` |  | nvarchar(255) | Y |  |
| `dfpur_other` |  | nvarchar(255) | Y |  |
| `dfpur_total` |  | float | Y |  |
| `dfpur_hdn_statuscode` |  | nvarchar(255) | Y |  |
| `dfpur_title` |  | nvarchar(255) | Y |  |
| `dfpur_sum` |  | float | Y |  |
| `dfpur_money` |  | float | Y |  |
| `dfpur_hdn_deptcode` |  | nvarchar(255) | Y |  |
| `dfpur_appkind` |  | nvarchar(255) | Y |  |
| `dfpur_status` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |

#### `testdfrequest` — （無中文名）　(列數約 1)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `dfreq_no` |  | nvarchar(255) | Y |  |
| `dfreq_deptname` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `hdndfreq_typename` |  | nvarchar(255) | Y |  |
| `dfreq_hdn_edesc` |  | nvarchar(255) | Y |  |
| `dfreq_usercode` |  | nvarchar(255) | Y |  |
| `dfreq_type` |  | nvarchar(255) | Y |  |
| `dfreq_desc` |  | nvarchar(255) | Y |  |
| `dfreq_title` |  | nvarchar(255) | Y |  |
| `dfreq_finaldate` |  | datetime | Y |  |
| `dfreq_appdate` |  | nvarchar(255) | Y |  |
| `dfreq_deptcode` |  | nvarchar(255) | Y |  |
| `dfreq_hdn_username` |  | nvarchar(255) | Y |  |
| `dfreq_hdn_boss` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `dfreq_hdn_deptOID` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |

### 前綴 `Cri` — —（7 表）


#### `CriticalProcessHintFields` — （無中文名）　(列數約 6)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `criticalProcessDefOID` |  | nchar(32) | Y |  |
| `fieldId` |  | varchar(255) | Y |  |
| `fieldDesc` |  | varchar(255) | Y |  |
| `creatorOID` |  | nchar(32) | Y |  |
| `createdTime` |  | datetime | Y |  |
| `updaterOID` |  | nchar(32) | Y |  |
| `updateTime` |  | datetime | Y |  |

#### `CriticalMessageLog` — （無中文名）　(列數約 5)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `criticalFromOID` |  | nchar(32) | Y |  |
| `criticalMessageKey` |  | nvarchar(255) | Y |  |
| `priorityId` |  | int | Y | FK? |
| `serialNumber` |  | nvarchar(100) | Y |  |
| `processInstanceOID` |  | nchar(32) | Y |  |
| `fieldData` |  | varchar(1000) | Y |  |
| `creatorOID` |  | nchar(32) | Y |  |
| `createdTime` |  | datetime | Y |  |
| `updaterOID` |  | nchar(32) | Y |  |
| `updateTime` |  | datetime | Y |  |

> 隱含關聯：[隱含FK→ priorityId→CriticalPriority]

#### `CriticalConditionDefinition` — （無中文名）　(列數約 2)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `conditionType` |  | nvarchar(50) | Y |  |
| `content` |  | ntext | Y |  |

#### `CriticalDefinition` — （無中文名）　(列數約 2)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `objectVersion` |  | int | N |  |
| `criticalId` |  | varchar(10) | N | PK |
| `criticalName` |  | nvarchar(255) | Y |  |
| `creatorOID` |  | nchar(32) | Y |  |
| `createdTime` |  | datetime | Y |  |
| `updaterOID` |  | nchar(32) | Y |  |
| `updateTime` |  | datetime | Y |  |

#### `CriticalFocusProcess` — （無中文名）　(列數約 2)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `userOID` |  | nchar(32) | Y |  |
| `processPackageId` |  | nvarchar(255) | Y |  |
| `creatorOID` |  | nchar(32) | Y |  |
| `createdTime` |  | datetime | Y |  |
| `updaterOID` |  | nchar(32) | Y |  |
| `updateTime` |  | datetime | Y |  |

#### `CriticalPriority` — （無中文名）　(列數約 2)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `objectVersion` |  | int | N |  |
| `priorityId` |  | int | N | PK |
| `priorityName` |  | nvarchar(255) | Y |  |
| `creatorOID` |  | nchar(32) | Y |  |
| `createdTime` |  | datetime | Y |  |
| `updaterOID` |  | nchar(32) | Y |  |
| `updateTime` |  | datetime | Y |  |

#### `CriticalProcessDefinition` — （無中文名）　(列數約 2)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `processPackageId` |  | nvarchar(255) | Y |  |
| `criticalId` |  | varchar(10) | Y | FK? |
| `criticalMessageKey` |  | nvarchar(255) | Y |  |
| `priorityId` |  | int | Y | FK? |
| `conditionDefinitionOID` |  | nchar(32) | Y |  |
| `creatorOID` |  | nchar(32) | Y |  |
| `createdTime` |  | datetime | Y |  |
| `updaterOID` |  | nchar(32) | Y |  |
| `updateTime` |  | datetime | Y |  |

> 隱含關聯：[隱含FK→ criticalId→CriticalDefinition, priorityId→CriticalPriority]

### 前綴 `ecp` — 入口/雲端平台（21 表）


#### `ecp_module_page` — （無中文名）　(列數約 9)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `oid` |  | nchar(32) | N | PK |
| `module_oid` |  | nvarchar(32) | Y |  |
| `page_oid` |  | nvarchar(32) | Y |  |
| `creator_uid` |  | nvarchar(32) | Y |  |
| `creator_date` |  | datetime | Y |  |
| `modify_uid` |  | nvarchar(32) | Y |  |
| `modify_date` |  | datetime | Y |  |
| `flag` |  | numeric(8,0) | Y |  |
| `page_name` |  | nvarchar(255) | Y |  |

#### `ecp_page_module` — （無中文名）　(列數約 9)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `oid` |  | nchar(32) | N | PK |
| `module_id` |  | nvarchar(32) | Y |  |
| `is_show` |  | nvarchar(8) | Y |  |
| `name_cn` |  | nvarchar(255) | N |  |
| `name_tw` |  | nvarchar(255) | N |  |
| `name_en` |  | nvarchar(255) | N |  |
| `path` |  | nvarchar(255) | Y |  |
| `apply_page` |  | nvarchar(8) | Y |  |
| `description` |  | nvarchar(255) | Y |  |
| `creator_id` |  | nvarchar(32) | Y |  |
| `creator_name` |  | nvarchar(32) | Y |  |
| `create_time` |  | datetime | Y |  |
| `creator_uid` |  | nvarchar(32) | Y |  |
| `creator_date` |  | datetime | Y |  |
| `modify_uid` |  | nvarchar(32) | Y |  |
| `modify_date` |  | datetime | Y |  |
| `flag` |  | numeric(8,0) | Y |  |
| `RES04` |  | nvarchar(255) | Y |  |
| `RES05` |  | nvarchar(255) | Y |  |
| `RES06` |  | nvarchar(255) | Y |  |
| `RES07` |  | nvarchar(255) | Y |  |
| `RES08` |  | nvarchar(255) | Y |  |

#### `ecp_page_basic` — （無中文名）　(列數約 1)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `oid` |  | nchar(32) | N | PK |
| `page_id` |  | nvarchar(32) | N |  |
| `is_show` |  | nvarchar(8) | Y |  |
| `name_cn` |  | nvarchar(255) | Y |  |
| `name_tw` |  | nvarchar(255) | Y |  |
| `name_en` |  | nvarchar(255) | Y |  |
| `sort_numb` |  | numeric(8,0) | Y |  |
| `is_customization` |  | nvarchar(8) | Y |  |
| `show_range` |  | nvarchar(8) | Y |  |
| `description` |  | nvarchar(255) | Y |  |
| `background_color` |  | nvarchar(32) | Y |  |
| `creator_id` |  | nvarchar(32) | Y |  |
| `creator_name` |  | nvarchar(32) | Y |  |
| `create_time` |  | datetime | Y |  |
| `creator_uid` |  | nvarchar(32) | Y |  |
| `creator_date` |  | datetime | Y |  |
| `modify_uid` |  | nvarchar(32) | Y |  |
| `modify_date` |  | datetime | Y |  |
| `flag` |  | numeric(8,0) | Y |  |
| `layout` |  | ntext | Y |  |
| `RES04` |  | nvarchar(255) | Y |  |
| `RES05` |  | nvarchar(255) | Y |  |
| `RES06` |  | nvarchar(255) | Y |  |
| `RES07` |  | nvarchar(255) | Y |  |
| `RES08` |  | nvarchar(255) | Y |  |

#### `ecp_page_range` — （無中文名）　(列數約 1)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `oid` |  | nchar(32) | N | PK |
| `page_oid` |  | nvarchar(32) | Y |  |
| `show_range` |  | nvarchar(32) | Y |  |
| `creator_uid` |  | nvarchar(32) | Y |  |
| `creator_date` |  | datetime | Y |  |
| `modify_uid` |  | nvarchar(32) | Y |  |
| `modify_date` |  | datetime | Y |  |
| `flag` |  | numeric(8,0) | Y |  |
| `source_oid` |  | nvarchar(32) | Y |  |
| `source_id` |  | nvarchar(32) | Y |  |
| `source_name` |  | nvarchar(32) | Y |  |

#### `ecp_anc_info` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `oid` |  | nchar(32) | N | PK |
| `type_oid` |  | nvarchar(32) | N |  |
| `title` |  | nvarchar(255) | N |  |
| `summary` |  | nvarchar(255) | Y |  |
| `anc_time` |  | nvarchar(32) | N |  |
| `start_time` |  | datetime | Y |  |
| `end_time` |  | datetime | Y |  |
| `range` |  | nvarchar(8) | N |  |
| `processsn` |  | nvarchar(200) | Y |  |
| `status` |  | nvarchar(8) | Y |  |
| `att_numb` |  | numeric(8,0) | Y |  |
| `reading_numb` |  | numeric(10,0) | Y |  |
| `creator_id` |  | nvarchar(32) | Y |  |
| `creator_name` |  | nvarchar(32) | Y |  |
| `create_time` |  | datetime | Y |  |
| `editor_id` |  | nvarchar(32) | Y |  |
| `editor_name` |  | nvarchar(32) | Y |  |
| `edit_time` |  | datetime | Y |  |
| `is_upload_img` |  | nvarchar(8) | Y |  |
| `creator_uid` |  | nvarchar(32) | Y |  |
| `creator_date` |  | datetime | Y |  |
| `modify_uid` |  | nvarchar(32) | Y |  |
| `modify_date` |  | datetime | Y |  |
| `flag` |  | numeric(8,0) | Y |  |
| `context` |  | ntext | Y |  |
| `pushAppId` |  | nvarchar(32) | Y |  |

#### `ecp_anc_range` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `oid` |  | nchar(32) | N | PK |
| `anc_oid` |  | nvarchar(32) | Y |  |
| `source_oid` |  | nvarchar(50) | Y |  |
| `creator_uid` |  | nvarchar(32) | Y |  |
| `creator_date` |  | date | Y |  |
| `modfiy_uid` |  | nvarchar(32) | Y |  |
| `modfiy_date` |  | date | Y |  |
| `flag` |  | numeric(8,0) | Y |  |
| `source_id` |  | nvarchar(32) | Y |  |
| `source_name` |  | nvarchar(32) | Y |  |
| `show_range` |  | nvarchar(32) | Y |  |

#### `ecp_anc_type` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `oid` |  | nchar(32) | N | PK |
| `type_id` |  | nvarchar(32) | N |  |
| `type_name` |  | nvarchar(255) | N |  |
| `is_public` |  | nvarchar(8) | N |  |
| `description` |  | nvarchar(255) | Y |  |
| `create_time` |  | datetime | Y |  |
| `create_id` |  | nvarchar(32) | Y |  |
| `create_name` |  | nvarchar(32) | Y |  |
| `creator_uid` |  | nvarchar(32) | Y |  |
| `creator_date` |  | datetime | Y |  |
| `modify_uid` |  | nvarchar(32) | Y |  |
| `modify_date` |  | datetime | Y |  |
| `flag` |  | numeric(8,0) | Y |  |

#### `ecp_anc_type_range` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `oid` |  | nchar(32) | N | PK |
| `anc_type_oid` |  | nvarchar(32) | Y |  |
| `source_oid` |  | nvarchar(50) | Y |  |
| `creator_uid` |  | nvarchar(32) | Y |  |
| `creator_date` |  | datetime | Y |  |
| `modfiy_uid` |  | nvarchar(32) | Y |  |
| `modfiy_date` |  | datetime | Y |  |
| `flag` |  | numeric(8,0) | Y |  |
| `source_id` |  | nvarchar(32) | Y |  |
| `source_name` |  | nvarchar(32) | Y |  |
| `show_range` |  | nvarchar(32) | Y |  |

#### `ecp_anc_view_record` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `oid` |  | nchar(32) | N | PK |
| `anc_oid` |  | nvarchar(32) | N |  |
| `viewer_oid` |  | nvarchar(32) | N |  |
| `view_times` |  | int | N |  |
| `last_view_time` |  | datetime | N |  |

#### `ecp_attachment` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `oid` |  | nchar(32) | N | PK |
| `name` |  | nvarchar(255) | N |  |
| `type` |  | nvarchar(32) | N |  |
| `content_type` |  | nvarchar(255) | Y |  |
| `source_oid` |  | nchar(32) | Y |  |
| `file_size` |  | float | Y |  |
| `source_type` |  | nvarchar(8) | Y |  |
| `create_id` |  | nvarchar(32) | Y |  |
| `create_name` |  | nvarchar(32) | Y |  |
| `create_time` |  | datetime | Y |  |
| `creator_uid` |  | nvarchar(32) | Y |  |
| `creator_date` |  | datetime | Y |  |
| `modify_uid` |  | nvarchar(32) | Y |  |
| `modify_date` |  | datetime | Y |  |
| `flag` |  | numeric(8,0) | Y |  |
| `attachment_source` |  | nvarchar(8) | Y |  |
| `noCmDocument_oid` |  | nchar(32) | Y |  |
| `temp_name` |  | nvarchar(255) | Y |  |

#### `ecp_chart` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `oid` |  | nchar(32) | N | PK |
| `chart_id` |  | nvarchar(32) | Y |  |
| `name_cn` |  | nvarchar(255) | N |  |
| `name_tw` |  | nvarchar(255) | N |  |
| `name_en` |  | nvarchar(255) | N |  |
| `is_show` |  | varchar(8) | Y |  |
| `show_range` |  | varchar(8) | Y |  |
| `data_source` |  | varchar(8) | Y |  |
| `data_engine` |  | nvarchar(8) | Y |  |
| `data_connect` |  | nvarchar(255) | Y |  |
| `query_sql` |  | ntext | Y |  |
| `data_form` |  | nvarchar(255) | Y |  |
| `data_structure` |  | ntext | Y |  |
| `creator_id` |  | nvarchar(32) | Y |  |
| `creator_name` |  | nvarchar(255) | Y |  |
| `create_time` |  | datetime | Y |  |
| `RES04` |  | nvarchar(255) | Y |  |
| `RES05` |  | nvarchar(255) | Y |  |
| `RES06` |  | nvarchar(255) | Y |  |
| `RES07` |  | nvarchar(255) | Y |  |
| `RES08` |  | nvarchar(255) | Y |  |
| `creator_uid` |  | nvarchar(32) | Y |  |
| `creator_date` |  | datetime | Y |  |
| `modify_uid` |  | nvarchar(32) | Y |  |
| `modify_date` |  | datetime | Y |  |
| `flag` |  | numeric(8,0) | Y |  |
| `template_type` |  | nvarchar(255) | Y |  |

#### `ecp_chart_range` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `oid` |  | nchar(32) | N | PK |
| `chart_oid` |  | nvarchar(32) | N |  |
| `show_range` |  | varchar(8) | Y |  |
| `source_oid` |  | nvarchar(32) | Y |  |
| `source_id` |  | nvarchar(32) | Y |  |
| `source_name` |  | nvarchar(255) | Y |  |
| `creator_uid` |  | nvarchar(32) | Y |  |
| `creator_date` |  | datetime | Y |  |
| `modify_uid` |  | nvarchar(32) | Y |  |
| `modify_date` |  | datetime | Y |  |
| `flag` |  | numeric(8,0) | Y |  |

#### `ecp_link` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `oid` |  | nchar(32) | N | PK |
| `link_id` |  | nvarchar(32) | N |  |
| `name_cn` |  | nvarchar(255) | N |  |
| `name_tw` |  | nvarchar(255) | N |  |
| `name_en` |  | nvarchar(255) | N |  |
| `link_path` |  | nvarchar(255) | N |  |
| `sort_numb` |  | numeric(8,0) | N |  |
| `creator_id` |  | nvarchar(32) | N |  |
| `creator_name` |  | nvarchar(32) | N |  |
| `create_time` |  | datetime | N |  |
| `creator_uid` |  | numeric(32,0) | Y |  |
| `creator_date` |  | datetime | Y |  |
| `modify_uid` |  | nvarchar(32) | Y |  |
| `modify_date` |  | datetime | Y |  |
| `flag` |  | numeric(8,0) | Y |  |
| `RES04` |  | nvarchar(255) | Y |  |
| `RES05` |  | nvarchar(255) | Y |  |
| `RES06` |  | nvarchar(255) | Y |  |
| `RES07` |  | nvarchar(255) | Y |  |
| `RES08` |  | nvarchar(255) | Y |  |
| `link_type` |  | numeric(8,0) | N |  |

#### `ecp_product` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `oid` |  | nchar(32) | N | PK |
| `name_cn` |  | nvarchar(255) | N |  |
| `spec` |  | nvarchar(255) | Y |  |
| `remarks` |  | nvarchar(255) | Y |  |
| `creator_id` |  | nvarchar(32) | N |  |
| `creator_name` |  | nvarchar(32) | N |  |
| `create_time` |  | datetime | N |  |
| `creator_uid` |  | nvarchar(32) | Y |  |
| `creator_date` |  | datetime | Y |  |
| `modif_uid` |  | nvarchar(32) | Y |  |
| `modify_date` |  | datetime | Y |  |
| `flag` |  | numeric(8,0) | Y |  |
| `RES04` |  | nvarchar(255) | Y |  |
| `RES05` |  | nvarchar(255) | Y |  |
| `RES06` |  | nvarchar(255) | Y |  |
| `RES07` |  | nvarchar(255) | Y |  |
| `RES08` |  | nvarchar(255) | Y |  |
| `name_tw` |  | nvarchar(255) | N |  |
| `name_en` |  | nvarchar(255) | N |  |

#### `ecp_schedule` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `oid` |  | nchar(32) | N | PK |
| `name` |  | nvarchar(200) | Y |  |
| `location` |  | nvarchar(255) | Y |  |
| `time_flag` |  | nvarchar(8) | Y |  |
| `start_time` |  | datetime | Y |  |
| `end_time` |  | datetime | Y |  |
| `emergency` |  | nvarchar(8) | Y |  |
| `participant_flag` |  | nvarchar(8) | Y |  |
| `description` |  | nvarchar(255) | Y |  |
| `source` |  | nvarchar(8) | Y |  |
| `creator_oid` |  | nvarchar(32) | Y |  |
| `creator_id` |  | nvarchar(100) | Y |  |
| `creator_name` |  | nvarchar(100) | Y |  |
| `create_time` |  | datetime | Y |  |
| `creator_uid` |  | nvarchar(32) | Y |  |
| `creator_date` |  | datetime | Y |  |
| `modify_uid` |  | nvarchar(32) | Y |  |
| `modify_date` |  | datetime | Y |  |
| `flag` |  | numeric(8,0) | Y |  |
| `link` |  | nvarchar(255) | Y |  |
| `type` |  | nvarchar(8) | Y |  |
| `repeat_setting` |  | nvarchar(8) | Y |  |
| `repeat_count` |  | numeric(8,0) | Y |  |
| `repeat_deadline` |  | datetime | Y |  |

#### `ecp_schedule_range` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `oid` |  | nchar(32) | N | PK |
| `schedule_oid` |  | nchar(32) | Y |  |
| `person_oid` |  | nchar(32) | Y |  |
| `person_id` |  | nvarchar(100) | Y |  |
| `person_name` |  | nvarchar(100) | Y |  |
| `creator_oid` |  | nchar(32) | Y |  |
| `creator_name` |  | nvarchar(100) | Y |  |
| `start_time` |  | datetime | Y |  |
| `end_time` |  | datetime | Y |  |
| `creator_uid` |  | varchar(32) | Y |  |
| `creator_date` |  | datetime | Y |  |
| `modify_uid` |  | nvarchar(32) | Y |  |
| `modify_date` |  | datetime | Y |  |
| `flag` |  | numeric(8,0) | Y |  |
| `source` |  | nvarchar(8) | Y |  |

#### `ecp_schedule_type` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `oid` |  | nchar(32) | N | PK |
| `type_id` |  | nvarchar(32) | Y |  |
| `type_name` |  | nvarchar(255) | Y |  |
| `is_valid` |  | nvarchar(8) | Y |  |
| `color` |  | nvarchar(32) | Y |  |
| `creator_time` |  | datetime | Y |  |
| `creator_id` |  | nvarchar(32) | Y |  |
| `creator_name` |  | nvarchar(32) | Y |  |
| `creator_uid` |  | nvarchar(32) | Y |  |
| `creator_date` |  | datetime | Y |  |
| `modify_uid` |  | nvarchar(32) | Y |  |
| `modify_date` |  | datetime | Y |  |
| `flag` |  | numeric(8,0) | Y |  |

#### `ecp_schedule_type_range` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `oid` |  | nchar(32) | N | PK |
| `type_oid` |  | nchar(32) | Y |  |
| `source_oid` |  | nchar(32) | Y |  |
| `source_id` |  | nvarchar(32) | Y |  |
| `source_name` |  | nvarchar(32) | Y |  |
| `authority` |  | nvarchar(8) | Y |  |
| `show_range` |  | nvarchar(32) | Y |  |
| `creator_uid` |  | nvarchar(32) | Y |  |
| `creator_date` |  | datetime | Y |  |
| `modify_uid` |  | nvarchar(32) | Y |  |
| `modify_date` |  | datetime | Y |  |
| `flag` |  | numeric(8,0) | Y |  |

#### `ecp_schedule_type_relation` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `oid` |  | nchar(32) | N | PK |
| `type_oid` |  | nchar(32) | Y |  |
| `schedule_oid` |  | nchar(32) | Y |  |
| `type_name` |  | nvarchar(255) | Y |  |
| `creator_uid` |  | nvarchar(32) | Y |  |
| `creator_date` |  | datetime | Y |  |
| `modify_uid` |  | nvarchar(32) | Y |  |
| `modify_date` |  | datetime | Y |  |
| `flag` |  | numeric(8,0) | Y |  |

#### `ecp_source_connect` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `oid` |  | nchar(32) | N | PK |
| `chart_oid` |  | nvarchar(32) | N |  |
| `ip` |  | varchar(32) | N |  |
| `port` |  | varchar(8) | Y |  |
| `init_database` |  | varchar(32) | Y |  |
| `username` |  | nvarchar(32) | N |  |
| `password` |  | nvarchar(255) | N |  |
| `creator_id` |  | nvarchar(32) | N |  |
| `creator_name` |  | nvarchar(255) | N |  |
| `create_time` |  | datetime | N |  |
| `creator_uid` |  | nvarchar(32) | Y |  |
| `creator_date` |  | datetime | Y |  |
| `modify_uid` |  | nvarchar(32) | Y |  |
| `modify_date` |  | datetime | Y |  |
| `flag` |  | numeric(8,0) | Y |  |

#### `ecp_tool_dl` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `oid` |  | nchar(32) | N | PK |
| `name_cn` |  | nvarchar(255) | N |  |
| `description` |  | nvarchar(255) | N |  |
| `creator_id` |  | nvarchar(32) | N |  |
| `creator_name` |  | nvarchar(32) | N |  |
| `create_time` |  | datetime | N |  |
| `creator_uid` |  | nvarchar(32) | Y |  |
| `creator_date` |  | datetime | Y |  |
| `modify_uid` |  | nvarchar(32) | Y |  |
| `modify_date` |  | datetime | Y |  |
| `flag` |  | numeric(8,0) | Y |  |
| `RES04` |  | nvarchar(255) | Y |  |
| `RES05` |  | nvarchar(255) | Y |  |
| `RES06` |  | nvarchar(255) | Y |  |
| `RES07` |  | nvarchar(255) | Y |  |
| `RES08` |  | nvarchar(255) | Y |  |
| `name_tw` |  | nvarchar(255) | N |  |
| `name_en` |  | nvarchar(255) | N |  |

### 前綴 `Fav` — —（2 表）


#### `FavoriteProcess` — （無中文名）　(列數約 13)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nvarchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `userOID` |  | nvarchar(32) | N |  |
| `processID` |  | nvarchar(100) | N |  |
| `sequence` |  | int | N |  |

#### `FavoriteMenu` — （無中文名）　(列數約 4)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nvarchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `userOID` |  | nvarchar(32) | N |  |
| `menuMark` |  | nvarchar(100) | N |  |
| `accessType` |  | nvarchar(50) | N |  |
| `isMain` |  | int | N |  |
| `sequence` |  | int | N |  |

### 前綴 `dfd` — —（1 表）


#### `dfdocument` — （無中文名）　(列數約 15)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `DT1` |  | datetime | Y |  |
| `HDATE` |  | nvarchar(255) | Y |  |
| `RB1` |  | nvarchar(255) | Y |  |
| `TB1` |  | nvarchar(255) | Y |  |
| `DT2` |  | datetime | Y |  |
| `HT1` |  | nvarchar(255) | Y |  |
| `TA2` |  | nvarchar(255) | Y |  |
| `TB3` |  | nvarchar(255) | Y |  |
| `TA1` |  | nvarchar(255) | Y |  |
| `TB2` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `TB5` |  | nvarchar(255) | Y |  |
| `TB4` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `DD3` |  | nvarchar(255) | Y |  |
| `SN1` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `HDEPT` |  | nvarchar(255) | Y |  |
| `TB6` |  | nvarchar(255) | Y |  |
| `HT2` |  | nvarchar(255) | Y |  |

### 前綴 `JMS` — —（5 表）


#### `JMS_ROLES` — （無中文名）　(列數約 9)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `ROLEID` |  | varchar(32) | N | PK |
| `USERID` |  | varchar(32) | N | PK |

> 隱含關聯：[隱含FK→ USERID→JMS_USERS]

#### `JMS_USERS` — （無中文名）　(列數約 5)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `USERID` |  | varchar(32) | N | PK |
| `PASSWD` |  | varchar(32) | N |  |
| `CLIENTID` |  | varchar(128) | Y |  |

#### `JMS_MESSAGES` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `MESSAGEID` |  | int | N |  |
| `DESTINATION` |  | varchar(150) | N |  |
| `TXID` |  | int | Y | FK? |
| `TXOP` |  | char(1) | Y |  |
| `MESSAGEBLOB` |  | image | Y |  |

> 隱含關聯：[隱含FK→ TXID→JMS_TRANSACTIONS]

#### `JMS_SUBSCRIPTIONS` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `CLIENTID` |  | varchar(128) | N | PK |
| `SUBNAME` |  | varchar(128) | N | PK |
| `TOPIC` |  | varchar(255) | N |  |
| `SELECTOR` |  | varchar(255) | Y |  |

#### `JMS_TRANSACTIONS` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `TXID` |  | int | N | PK |

### 前綴 `Trm` — —（7 表）


#### `TrmProperties` — （無中文名）　(列數約 10)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `paraKey` |  | nvarchar(256) | Y |  |
| `paraValue` |  | ntext | Y |  |
| `objectVersion` |  | int | Y |  |
| `createdTime` |  | datetime | Y |  |
| `creatorOID` |  | nchar(32) | Y |  |
| `updatedTime` |  | datetime | Y |  |
| `updaterOID` |  | nchar(32) | Y |  |

#### `TrmSourceForm` — （無中文名）　(列數約 1)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `createdTime` |  | datetime | Y |  |
| `creatorOID` |  | nchar(32) | Y |  |
| `updatedTime` |  | datetime | Y |  |
| `updaterOID` |  | nchar(32) | Y |  |
| `nanaFormId` |  | nvarchar(30) | N |  |
| `nanaFormName` |  | nvarchar(50) | Y |  |
| `nanaFormColumnSet` |  | ntext | N |  |

#### `TrmCompanyMapping` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `organizationOID` |  | nchar(32) | N |  |
| `departmentOID` |  | nchar(32) | N |  |
| `erpCompany` |  | nvarchar(50) | N |  |
| `exclusiveRegion` |  | nvarchar(1) | N |  |
| `objectVersion` |  | int | Y |  |
| `createdTime` |  | datetime | Y |  |
| `creatorOID` |  | nchar(32) | Y |  |
| `updatedTime` |  | datetime | Y |  |
| `updaterOID` |  | nchar(32) | Y |  |

#### `TrmConversionFunction` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `createdTime` |  | datetime | Y |  |
| `creatorOID` |  | nchar(32) | Y |  |
| `updatedTime` |  | datetime | Y |  |
| `updaterOID` |  | nchar(32) | Y |  |
| `functionId` |  | nvarchar(30) | N |  |
| `functionName` |  | nvarchar(50) | Y |  |
| `isStandard` |  | nvarchar(1) | N |  |
| `remark` |  | ntext | Y |  |

#### `TrmConversionFunctionData` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `createdTime` |  | datetime | Y |  |
| `creatorOID` |  | nchar(32) | Y |  |
| `updatedTime` |  | datetime | Y |  |
| `updaterOID` |  | nchar(32) | Y |  |
| `containerOID` |  | nchar(32) | N |  |
| `sourceValue` |  | nvarchar(50) | N |  |
| `targetValue` |  | nvarchar(50) | Y |  |
| `illustrate` |  | nvarchar(250) | Y |  |

#### `TrmInitiateProcessProfile` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `createdTime` |  | datetime | Y |  |
| `creatorOID` |  | nchar(32) | Y |  |
| `updatedTime` |  | datetime | Y |  |
| `updaterOID` |  | nchar(32) | Y |  |
| `nanaFormId` |  | nvarchar(30) | N |  |
| `nanaFormName` |  | nvarchar(50) | Y |  |
| `targetProcessId` |  | nvarchar(100) | N |  |
| `isStandard` |  | nvarchar(1) | N |  |
| `subject` |  | nvarchar(200) | Y |  |
| `mappingJson` |  | ntext | N |  |

#### `TrmInitiateRecord` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `createdTime` |  | datetime | Y |  |
| `creatorOID` |  | nchar(32) | Y |  |
| `updatedTime` |  | datetime | Y |  |
| `updaterOID` |  | nchar(32) | Y |  |
| `telnetId` |  | nvarchar(30) | N |  |
| `nanaFormId` |  | nvarchar(30) | N |  |
| `nanaFormNo` |  | nvarchar(50) | N |  |
| `processDefinitionId` |  | nvarchar(100) | N |  |
| `processSerialNumber` |  | nvarchar(100) | Y |  |
| `invokeJson` |  | ntext | N |  |
| `executionResult` |  | nvarchar(1) | N |  |
| `failNumber` |  | int | N |  |
| `firstInvokeDateTime` |  | datetime | Y |  |
| `lastInvokeDateTime` |  | datetime | Y |  |
| `failDescription` |  | ntext | Y |  |

### 前綴 `dfu` — —（3 表）


#### `dfusual` — （無中文名）　(列數約 8)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `dfusual_hdn_username` |  | nvarchar(255) | Y |  |
| `dfusual_applydate` |  | datetime | Y |  |
| `dfusual_usercode` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `dfusual_title` |  | nvarchar(255) | Y |  |
| `dfusual_suggest` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `dfusual_desc` |  | nvarchar(255) | Y |  |
| `dfusual_deptname` |  | nvarchar(255) | Y |  |
| `dfusual_hdn_deptcode` |  | nvarchar(255) | Y |  |

#### `dfunusual_16` — （無中文名）　(列數約 1)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `DT1` |  | datetime | Y |  |
| `RB1` |  | nvarchar(255) | Y |  |
| `TB1` |  | nvarchar(255) | Y |  |
| `RB2` |  | nvarchar(255) | Y |  |
| `TB3` |  | nvarchar(255) | Y |  |
| `TB2` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `TB5` |  | nvarchar(255) | Y |  |
| `TB4` |  | nvarchar(255) | Y |  |
| `TB7` |  | nvarchar(255) | Y |  |
| `TB6` |  | nvarchar(255) | Y |  |
| `TB10` |  | nvarchar(255) | Y |  |
| `TB9` |  | nvarchar(255) | Y |  |
| `TB8` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `SN1` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |

#### `dfunusual_20` — （無中文名）　(列數約 1)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `DT1` |  | datetime | Y |  |
| `RB1` |  | nvarchar(255) | Y |  |
| `TB1` |  | nvarchar(255) | Y |  |
| `DT2` |  | datetime | Y |  |
| `RB2` |  | nvarchar(255) | Y |  |
| `TB2` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `TB5` |  | nvarchar(255) | Y |  |
| `TB4` |  | nvarchar(255) | Y |  |
| `TB7` |  | nvarchar(255) | Y |  |
| `TB6` |  | nvarchar(255) | Y |  |
| `TB10` |  | nvarchar(255) | Y |  |
| `TB9` |  | nvarchar(255) | Y |  |
| `TB8` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `SN1` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |

### 前綴 `Int` — —（4 表）


#### `IntegratedSessionBeanPara` — （無中文名）　(列數約 5)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `relevantDataDefId` |  | nvarchar(100) | N |  |
| `relevantDataDefName` |  | nvarchar(100) | Y |  |
| `containerOID` |  | nchar(32) | N |  |
| `relevantDataDefDesc` |  | ntext | Y |  |
| `initialValue` |  | nvarchar(1000) | Y |  |
| `isArray` |  | nvarchar(10) | N |  |
| `length` |  | int | Y |  |
| `dataType` |  | nvarchar(10) | N |  |
| `formalParameterId` |  | nvarchar(100) | N |  |
| `formalParameterName` |  | nvarchar(100) | Y |  |
| `parameterIndex` |  | int | N |  |
| `parameterMode` |  | nvarchar(50) | N |  |
| `formalParameterDesc` |  | ntext | Y |  |

#### `IntegratedSessionBeanApp` — （無中文名）　(列數約 2)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `id` |  | nvarchar(100) | N |  |
| `applicationDefinitionName` |  | nvarchar(100) | Y |  |
| `description` |  | ntext | Y |  |
| `homeClassName` |  | nvarchar(100) | N |  |
| `jndiName` |  | nvarchar(50) | N |  |
| `methodName` |  | nvarchar(50) | N |  |
| `serverIp` |  | nvarchar(50) | N |  |
| `serverPort` |  | nvarchar(10) | N |  |
| `serverType` |  | nvarchar(50) | N |  |
| `integratedSys` |  | nvarchar(100) | N |  |
| `serviceType` |  | nvarchar(20) | N |  |

#### `IntelligentLearningSchedule` — （無中文名）　(列數約 1)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | char(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `applicationId` |  | nvarchar(100) | N |  |
| `outliers` |  | int | N |  |

#### `IntelligentLearningRecord` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | char(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `performerOID` |  | nchar(32) | N |  |
| `processDefinitionId` |  | nvarchar(100) | N |  |
| `averageDealTime` |  | real | N |  |
| `averageActualDealTime` |  | real | N |  |
| `weight` |  | int | N |  |

### 前綴 `MTS` — 訊息/任務（12 表）


#### `MTSProperties` — （無中文名）　(列數約 4)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `paraKey` |  | nvarchar(100) | Y |  |
| `paraValue` |  | nvarchar(100) | Y |  |
| `manual` |  | char(1) | Y |  |
| `description` |  | nvarchar(2000) | Y |  |
| `paraType` |  | char(1) | Y |  |

#### `MTSParamFormat` — （無中文名）　(列數約 3)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `name` |  | nvarchar(100) | Y |  |
| `callAction` |  | nvarchar(100) | Y |  |
| `callType` |  | int | Y |  |
| `request` |  | nvarchar(2000) | Y |  |
| `url` |  | nvarchar(2000) | Y |  |
| `callFormat` |  | int | Y |  |
| `resourceTypeOID` |  | nchar(32) | Y |  |
| `creatorOID` |  | nchar(32) | Y |  |
| `updaterOID` |  | nchar(32) | Y |  |
| `createdTime` |  | datetime | Y |  |
| `updateTime` |  | datetime | Y |  |

#### `MTSResourceType` — （無中文名）　(列數約 1)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `resources` |  | int | Y |  |
| `resourceTypeId` |  | nvarchar(10) | Y |  |
| `resourceTypeName` |  | nvarchar(100) | Y |  |
| `creatorOID` |  | nchar(32) | Y |  |
| `updaterOID` |  | nchar(32) | Y |  |
| `createdTime` |  | datetime | Y |  |
| `updateTime` |  | datetime | Y |  |

#### `MTSMeetingApply` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `meetingSerialNumber` |  | nvarchar(100) | Y |  |
| `processInstOID` |  | nchar(32) | Y |  |
| `meetingTypeOID` |  | nchar(32) | Y |  |
| `applyUserOID` |  | nchar(32) | Y |  |
| `applyUserPhoneNumber` |  | nvarchar(100) | Y |  |
| `subject` |  | nvarchar(2000) | Y |  |
| `chairmanUserOID` |  | nchar(32) | Y |  |
| `chairmanOrgUnitOID` |  | nchar(32) | Y |  |
| `startTime` |  | datetime | Y |  |
| `endTime` |  | datetime | Y |  |
| `actualStartTime` |  | datetime | Y |  |
| `actualEndTime` |  | datetime | Y |  |
| `meetingGoal` |  | nvarchar(2000) | Y |  |
| `recorderUserOID` |  | nchar(32) | Y |  |
| `recorderOrgUnitOID` |  | nchar(32) | Y |  |
| `meetingUsers` |  | nvarchar(2000) | Y |  |
| `agenda` |  | nvarchar(2000) | Y |  |
| `status` |  | int | Y |  |
| `taskStatus` |  | int | Y |  |

#### `MTSMeetingApply_Tasks` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `meetingApplyOID` |  | nchar(32) | Y |  |
| `processInstOID` |  | nchar(32) | Y |  |
| `conclusion` |  | nvarchar(2000) | Y |  |
| `description` |  | nvarchar(2000) | Y |  |
| `taskManagerOID` |  | char(32) | Y |  |
| `taskManagerOrgUnitOID` |  | nchar(32) | Y |  |
| `estimatedCompletionDate` |  | datetime | Y |  |
| `actualCompletionDate` |  | datetime | Y |  |
| `taskStatus` |  | nvarchar(20) | Y |  |
| `taskResult` |  | nvarchar(2000) | Y |  |
| `taskClosure` |  | int | Y |  |
| `taskClosureDescription` |  | nvarchar(2000) | Y |  |

#### `MTSMeetingApply_Users` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `meetingApplyOID` |  | nchar(32) | Y |  |
| `participantOID` |  | nchar(32) | Y |  |
| `participantsOrgUnitOID` |  | nchar(32) | Y |  |
| `substituteParticipantOID` |  | nchar(32) | Y |  |
| `status` |  | int | Y |  |
| `attendTime` |  | datetime | Y |  |

#### `MTSMeetingType` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `meetingTypeId` |  | nvarchar(10) | Y |  |
| `meetingTypeName` |  | nvarchar(100) | Y |  |
| `sofeware` |  | nvarchar(100) | Y |  |
| `description` |  | nvarchar(2000) | Y |  |
| `creatorOID` |  | nchar(32) | Y |  |
| `updaterOID` |  | nchar(32) | Y |  |
| `createdTime` |  | datetime | Y |  |
| `updateTime` |  | datetime | Y |  |

#### `MTSResourceApply` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `resourceManagementOID` |  | nchar(32) | Y |  |
| `meetingApplyOID` |  | nchar(32) | Y |  |
| `meetingTypeOID` |  | nchar(32) | Y |  |
| `startTime` |  | datetime | Y |  |
| `endTime` |  | datetime | Y |  |
| `status` |  | int | Y |  |

#### `MTSResourceManagement` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `resources` |  | int | Y |  |
| `resourceId` |  | nvarchar(10) | N | PK |
| `resourceName` |  | nvarchar(100) | Y |  |
| `resourceLocation` |  | nvarchar(20) | Y |  |
| `description` |  | nvarchar(2000) | Y |  |
| `resourceTypeOID` |  | nchar(32) | Y |  |
| `seats` |  | int | Y |  |
| `webexParam` |  | nvarchar(2000) | Y |  |
| `creatorOID` |  | nchar(32) | Y |  |
| `updaterOID` |  | nchar(32) | Y |  |
| `createdTime` |  | datetime | Y |  |
| `updateTime` |  | datetime | Y |  |
| `isEnable` |  | int | Y |  |
| `resourceManagerOID` |  | nchar(32) | Y |  |
| `resourceOrder` |  | int | Y |  |

#### `MTSRoomApply` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `resourceManagementOID` |  | nchar(32) | Y |  |
| `meetingApplyOID` |  | nchar(32) | Y |  |
| `meetingTypeOID` |  | nchar(32) | Y |  |
| `startTime` |  | datetime | Y |  |
| `endTime` |  | datetime | Y |  |
| `status` |  | int | Y |  |
| `meetingKey` |  | nvarchar(100) | Y |  |
| `meetingPassword` |  | nvarchar(100) | Y |  |
| `meetingJoinUrl` |  | nvarchar(2000) | Y |  |
| `meetingHostKey` |  | nvarchar(100) | Y |  |

#### `MTSTemplate` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `templateId` |  | nvarchar(10) | Y |  |
| `templateName` |  | nvarchar(100) | Y |  |
| `applicantOID` |  | nchar(32) | Y |  |
| `title` |  | nvarchar(200) | Y |  |
| `chairmanOID` |  | nchar(32) | Y |  |
| `chairmanOrgUnitOID` |  | nchar(32) | Y |  |
| `recorderOID` |  | nchar(32) | Y |  |
| `recorderOrgUnitOID` |  | nchar(32) | Y |  |
| `validStartTime` |  | datetime | Y |  |
| `validEndTime` |  | datetime | Y |  |
| `description` |  | nvarchar(2000) | Y |  |
| `otherParticipantsUsers` |  | nvarchar(2000) | Y |  |
| `creatorOID` |  | nchar(32) | Y |  |
| `updaterOID` |  | nchar(32) | Y |  |
| `createdTime` |  | datetime | Y |  |
| `updateTime` |  | datetime | Y |  |

#### `MTSTemplate_Users` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `mtsTemplateOID` |  | nchar(32) | Y |  |
| `participantOID` |  | nchar(32) | Y |  |
| `participantsOrgUnitOID` |  | nchar(32) | Y |  |

### 前綴 `ISO` — ISO文件管理（28 表）


#### `ISOProperties` — （無中文名）　(列數約 6)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `paraKey` |  | nvarchar(50) | Y |  |
| `paraValue` |  | nvarchar(1000) | Y |  |
| `paraType` |  | char(1) | Y |  |
| `description` |  | nvarchar(200) | Y |  |

#### `ISOCloudProperties` — （無中文名）　(列數約 1)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | Y |  |
| `IAMApiUri` |  | nvarchar(200) | Y |  |
| `IAMSecretKey` |  | nvarchar(200) | Y |  |
| `cloudAPIUri` |  | nvarchar(200) | Y |  |
| `cloudUri` |  | nvarchar(200) | Y |  |
| `isEnabledSynCloud` |  | nvarchar(10) | Y |  |
| `temporaryCompanyAccount` |  | nvarchar(200) | Y |  |
| `fileType` |  | nvarchar(10) | Y |  |

#### `ISOAuthorityGroup` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `levelValue` |  | int | N |  |
| `authorizedTargetsString` |  | ntext | Y |  |
| `organizationUnitList` |  | ntext | Y |  |
| `groupList` |  | ntext | Y |  |
| `userList` |  | ntext | Y |  |
| `projectDefList` |  | ntext | Y |  |
| `organizationList` |  | ntext | Y |  |
| `docCategoryOID` |  | nchar(32) | Y |  |

#### `ISOAuthorityUsers` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `userOID` |  | nchar(32) | N |  |
| `docCategoryOID` |  | nchar(32) | N |  |
| `levelValue` |  | int | N |  |
| `OID` |  | nchar(32) | N | PK |

#### `ISOClause` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | Y |  |
| `clauseNo` |  | nvarchar(100) | N |  |
| `clauseName` |  | nvarchar(255) | N |  |
| `isoDocTypeOID` |  | nchar(32) | N |  |
| `clauseContent` |  | ntext | N |  |

#### `ISOCloudApplyDocsChangeRecord` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | Y |  |
| `cloudApplyRecordOID` |  | nchar(32) | Y |  |
| `changeAction` |  | nvarchar(10) | Y |  |
| `documentDocNo` |  | nvarchar(100) | Y |  |
| `documentDocName` |  | nvarchar(255) | Y |  |
| `documentOldDisplayVersion` |  | nvarchar(20) | Y |  |
| `documentNewDisplayVersion` |  | nvarchar(20) | Y |  |
| `cloudFileChangeDate` |  | datetime | Y |  |
| `cloudFileChangeStatus` |  | nvarchar(1) | Y |  |
| `cloudFileChangeResult` |  | nvarchar(2000) | Y |  |

#### `ISOCloudApplyDocsRecord` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | Y |  |
| `ISODocmItemOID` |  | nchar(32) | Y |  |
| `documentOID` |  | nchar(32) | Y |  |
| `documentDocNo` |  | nvarchar(100) | Y |  |
| `documentDocName` |  | nvarchar(255) | Y |  |
| `documentDisplayVersion` |  | nvarchar(20) | Y |  |
| `applyType` |  | nvarchar(10) | Y |  |
| `applyReadCount` |  | int | Y |  |
| `applyReadHour` |  | float | Y |  |
| `applyStartDate` |  | nvarchar(10) | Y |  |
| `applyEndDate` |  | nvarchar(10) | Y |  |
| `applyStartTime` |  | nvarchar(10) | Y |  |
| `applyEndTime` |  | nvarchar(10) | Y |  |
| `cloudApplyRecordOID` |  | nvarchar(32) | Y |  |

#### `ISODocCmItem` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `id` |  | nvarchar(100) | N |  |
| `checkoutUserOID` |  | nchar(32) | Y |  |
| `securityLevelOID` |  | nchar(32) | N |  |
| `checkoutTime` |  | datetime | Y |  |
| `checkInTime` |  | datetime | Y |  |
| `lastVersion` |  | int | N |  |
| `preInvNodDate` |  | datetime | Y |  |
| `invNodDays` |  | int | N |  |
| `releasedVersion` |  | int | N |  |
| `actionStatus` |  | nvarchar(100) | N |  |
| `publicationStatus` |  | nvarchar(100) | N |  |
| `hoursOfReadable` |  | int | N |  |
| `startReadTime` |  | datetime | N |  |
| `endReadTime` |  | datetime | N |  |
| `categoryPostFix` |  | nvarchar(3) | Y |  |
| `docWaterMarkOID` |  | nchar(32) | Y |  |
| `vettingOID` |  | nchar(32) | Y |  |
| `nextVettingDate` |  | datetime | Y |  |
| `isNeedSendNotification` |  | nvarchar(100) | Y |  |
| `checkoutProcessInstanceSN` |  | nvarchar(50) | Y |  |

#### `ISODocLevel` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `id` |  | nvarchar(100) | N |  |
| `levelName` |  | nvarchar(100) | Y |  |
| `showPosition` |  | int | N |  |
| `isoDocTypeOID` |  | nchar(32) | Y |  |
| `snCode` |  | nvarchar(10) | Y |  |

#### `ISODocType` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `id` |  | nvarchar(100) | N |  |
| `typeName` |  | nvarchar(100) | N |  |
| `snCode` |  | nvarchar(10) | Y |  |

#### `ISOFile` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `fileName` |  | nvarchar(255) | N |  |
| `isConvert` |  | int | N |  |
| `documentOID` |  | nchar(32) | N |  |
| `extensionType` |  | nvarchar(10) | Y |  |
| `sourceFileOID` |  | nchar(32) | N |  |
| `physicalName` |  | nvarchar(255) | Y |  |
| `isIndexed` |  | int | N |  |
| `requiredToConvertPDF` |  | int | N |  |
| `PDFPassword` |  | nvarchar(20) | Y |  |
| `pdfSecurityType` |  | int | Y |  |
| `isIndexedV8` |  | int | Y |  |

#### `ISOFilePolicy` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `policyId` |  | nvarchar(50) | N |  |
| `policyName` |  | nvarchar(50) | N |  |
| `offlineDay` |  | int | Y |  |
| `canCopy` |  | int | Y |  |
| `canPrint` |  | int | Y |  |
| `canEdit` |  | int | Y |  |
| `canSaveUnencrypted` |  | int | Y |  |
| `canScreenshot` |  | int | Y |  |
| `validDateFrom` |  | datetime | Y |  |
| `validDateTo` |  | datetime | Y |  |

#### `ISOFilePolicyMAC` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `isoFilePolicyOID` |  | nchar(32) | N |  |
| `macAddress` |  | nchar(32) | N |  |

#### `ISOFilePolicyUnit` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `isoFilePolicyOID` |  | nchar(32) | N |  |
| `unitOID` |  | nchar(32) | N |  |
| `unitType` |  | int | Y |  |

#### `ISOFileReadingRecord` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `documentOID` |  | nchar(32) | N |  |
| `docNo` |  | nvarchar(100) | N | FK? |
| `docName` |  | nvarchar(255) | N |  |
| `displayVersion` |  | nvarchar(10) | N |  |
| `isoFileOID` |  | nchar(32) | N |  |
| `fileName` |  | nvarchar(255) | N |  |
| `userOID` |  | nchar(32) | N |  |
| `userId` |  | nvarchar(100) | N |  |
| `userName` |  | nvarchar(255) | N |  |
| `orgUnitOID` |  | nchar(32) | N |  |
| `orgUnitId` |  | nvarchar(100) | N |  |
| `orgUnitName` |  | nvarchar(255) | N |  |
| `startReadTime` |  | datetime | N |  |
| `endReadTime` |  | datetime | Y |  |
| `action` |  | nvarchar(50) | N |  |

> 隱含關聯：[隱含FK→ docNo→SYN_ISODocCmItem]

#### `ISOFullTextSearch` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `searchId` |  | nchar(32) | N |  |
| `docNo` |  | nvarchar(100) | Y | FK? |
| `version` |  | int | Y |  |
| `createdTime` |  | datetime | Y |  |

> 隱含關聯：[隱含FK→ docNo→SYN_ISODocCmItem]

#### `ISOPaperRecord` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `docNo` |  | nvarchar(100) | N | FK? |
| `docVersion` |  | int | N |  |
| `checkoutType` |  | nvarchar(10) | N |  |
| `checkoutId` |  | nvarchar(100) | N |  |
| `checkoutOrgId` |  | nvarchar(100) | N |  |
| `numbers` |  | int | N |  |
| `checkoutDate` |  | datetime | N |  |
| `checkinDate` |  | datetime | Y |  |
| `checkStatus` |  | nvarchar(10) | N |  |
| `note` |  | ntext | Y |  |
| `docDisplayVersion` |  | nvarchar(10) | N |  |
| `processSerialNumber` |  | nvarchar(50) | Y |  |

> 隱含關聯：[隱含FK→ docNo→SYN_ISODocCmItem]

#### `ISOPortabilityCloudApplyRecord` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | Y |  |
| `applyUserId` |  | nvarchar(100) | Y |  |
| `applyUserName` |  | nvarchar(100) | Y |  |
| `applyUnitId` |  | nvarchar(100) | Y |  |
| `applyUnitName` |  | nvarchar(100) | Y |  |
| `applyDate` |  | datetime | Y |  |
| `companyOID` |  | nchar(32) | Y |  |
| `companyId` |  | nvarchar(100) | Y |  |
| `companyName` |  | nvarchar(255) | Y |  |
| `companyType` |  | nvarchar(1) | Y |  |
| `contactPerson` |  | nvarchar(100) | Y |  |
| `contactMail` |  | nvarchar(100) | Y |  |
| `cloudAccount` |  | nvarchar(500) | Y |  |
| `requirementTitle` |  | nvarchar(100) | Y |  |
| `requirements` |  | nvarchar(500) | Y |  |
| `ipLimitContent` |  | nvarchar(500) | Y |  |
| `companyTimeZone` |  | nvarchar(10) | Y |  |
| `watermarkId` |  | nvarchar(100) | Y |  |
| `remark` |  | nvarchar(500) | Y |  |
| `shareCloudUsers` |  | nvarchar(500) | Y |  |
| `isRecover` |  | nvarchar(1) | Y |  |
| `cloudFileuploadDate` |  | datetime | Y |  |
| `cloudFileuploadStatus` |  | nvarchar(1) | Y |  |
| `cloudFileuploadResult` |  | nvarchar(2000) | Y |  |
| `cloudFileUploadId` |  | nvarchar(100) | Y |  |
| `processSerialNumber` |  | nvarchar(100) | Y |  |

#### `ISOPortabilityCloudRecord` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | Y |  |
| `docNo` |  | nvarchar(100) | Y | FK? |
| `docName` |  | nvarchar(100) | Y |  |
| `displayVersion` |  | nvarchar(10) | Y |  |
| `fileId` |  | nvarchar(80) | Y |  |
| `fileName` |  | nvarchar(255) | Y |  |
| `clientReadStart` |  | datetime | Y |  |
| `clientReadEnd` |  | datetime | Y |  |
| `clientReadIp` |  | nvarchar(50) | Y |  |
| `clientReadCompanyId` |  | nvarchar(100) | Y |  |
| `clientReadCompanyName` |  | nvarchar(255) | Y |  |
| `clientReadCompanyType` |  | nvarchar(10) | Y |  |
| `clientReadUser` |  | nvarchar(50) | Y |  |
| `clientTimeZone` |  | nvarchar(10) | Y |  |
| `serverReadStart` |  | nvarchar(50) | Y |  |
| `serverReadEnd` |  | nvarchar(50) | Y |  |

> 隱含關聯：[隱含FK→ docNo→SYN_ISODocCmItem]

#### `ISOPortabilityCloudUsers` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | Y |  |
| `companyOID` |  | nchar(32) | Y |  |
| `contactPerson` |  | nvarchar(30) | Y |  |
| `contactNumber` |  | nvarchar(20) | Y |  |
| `contactMail` |  | nvarchar(2000) | Y |  |
| `directions` |  | nvarchar(500) | Y |  |
| `cloudAccount` |  | nvarchar(60) | Y |  |

#### `ISOPortabilityCompany` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | Y |  |
| `companyId` |  | nvarchar(20) | Y |  |
| `companyName` |  | nvarchar(80) | Y |  |
| `taxIdNumber` |  | nvarchar(20) | Y |  |
| `contactPerson` |  | nvarchar(30) | Y |  |
| `contactNumber` |  | nvarchar(20) | Y |  |
| `contactMail` |  | nvarchar(2000) | Y |  |
| `confidentialityContract` |  | nvarchar(1) | Y |  |
| `remark` |  | nvarchar(500) | Y |  |
| `effective` |  | nvarchar(1) | Y |  |
| `mailLocale` |  | nvarchar(10) | Y |  |
| `ipLimitContent` |  | nvarchar(500) | Y |  |
| `companyTimeZone` |  | nvarchar(10) | Y |  |

#### `ISOPortabilityMailDesign` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | Y |  |
| `mailTemplateId` |  | nvarchar(20) | Y |  |
| `mailTemplateName` |  | nvarchar(80) | Y |  |
| `mailContent` |  | nvarchar(4000) | Y |  |
| `fileCapacityLimit` |  | real | Y |  |
| `fileDeliveryType` |  | nvarchar(10) | Y |  |
| `fileCompressedPasswordType` |  | nvarchar(20) | Y |  |
| `fileDefaultPassword` |  | nvarchar(50) | Y |  |

#### `ISOPortabilityRecord` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | Y |  |
| `companyOID` |  | nchar(32) | Y |  |
| `companyId` |  | nvarchar(20) | Y |  |
| `companyName` |  | nvarchar(80) | Y |  |
| `contactPerson` |  | nvarchar(30) | Y |  |
| `contactMail` |  | nvarchar(2000) | Y |  |
| `documentOID` |  | nchar(32) | Y |  |
| `applicantDate` |  | datetime | Y |  |
| `shippingDate` |  | datetime | Y |  |
| `shippingStatus` |  | nvarchar(2) | Y |  |
| `shippingRemark` |  | nvarchar(2000) | Y |  |
| `filePassword` |  | nvarchar(50) | Y |  |
| `requirements` |  | nvarchar(2000) | Y |  |
| `remark` |  | nvarchar(2000) | Y |  |
| `refProcessInstanceSN` |  | nvarchar(50) | Y |  |

#### `ISOTracingData` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | Y |  |
| `documentOID` |  | nchar(32) | Y |  |
| `checkoutUserOID` |  | nchar(32) | Y |  |
| `checkoutTime` |  | datetime | Y |  |

#### `ISOVettingRecord` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | Y |  |
| `documentOID` |  | nchar(32) | Y |  |
| `vettingDate` |  | datetime | Y |  |
| `descriptions` |  | nvarchar(2000) | Y |  |
| `docNo` |  | nvarchar(100) | Y | FK? |
| `version` |  | int | Y |  |
| `displayVersion` |  | nvarchar(10) | Y |  |
| `docName` |  | nvarchar(255) | Y |  |
| `vettingProcessId` |  | nvarchar(100) | Y |  |
| `vettingSerialNumber` |  | nvarchar(100) | Y |  |
| `vettingRequestorOID` |  | nchar(32) | Y |  |
| `vettingDeciderOID` |  | nchar(32) | Y |  |
| `unitType` |  | int | Y |  |
| `unitOID` |  | nchar(32) | Y |  |
| `vetting2ProcessId` |  | nvarchar(100) | Y |  |
| `vetting2SerialNumber` |  | nvarchar(100) | Y |  |
| `vettingResult` |  | int | Y |  |
| `vettingStatus` |  | int | Y |  |
| `vettingLog` |  | nvarchar(2000) | Y |  |
| `creatorOID` |  | nchar(32) | Y |  |
| `createdTime` |  | datetime | Y |  |
| `updaterOID` |  | nchar(32) | Y |  |
| `updateTime` |  | datetime | Y |  |

> 隱含關聯：[隱含FK→ docNo→SYN_ISODocCmItem]

#### `ISOVettingRule` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | Y |  |
| `vettingId` |  | nvarchar(10) | Y |  |
| `vettingRules` |  | nvarchar(100) | Y |  |
| `vettingPeriod` |  | int | Y |  |
| `unitType` |  | int | Y |  |
| `unitOID` |  | nchar(32) | Y |  |
| `vettingRequestorOID` |  | nchar(32) | Y |  |
| `exceptionNoticeType` |  | int | Y |  |
| `exceptionNoticeOID` |  | nchar(32) | Y |  |
| `vettingProcessId` |  | nvarchar(100) | Y |  |
| `modifyProcessId` |  | nvarchar(100) | Y |  |
| `abolishProcessId` |  | nvarchar(100) | Y |  |
| `creatorOID` |  | nchar(32) | Y |  |
| `createdTime` |  | datetime | Y |  |
| `updaterOID` |  | nchar(32) | Y |  |
| `updateTime` |  | datetime | Y |  |

#### `ISOWatermarkImagePattern` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | Y |  |
| `imageId` |  | nvarchar(200) | Y |  |
| `imageName` |  | nvarchar(200) | Y |  |
| `imageTransparency` |  | nvarchar(20) | Y |  |
| `imageGrayscale` |  | nvarchar(20) | Y |  |
| `imageWords` |  | nvarchar(2000) | Y |  |

#### `ISOWatermarkPattern` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | Y |  |
| `watermark` |  | nchar(5) | Y |  |
| `watermarkContext` |  | nvarchar(4000) | Y |  |
| `checkType` |  | nvarchar(20) | N |  |
| `checkValue` |  | nvarchar(50) | N |  |
| `watermarkAttribute` |  | nvarchar(300) | Y |  |
| `readwatermarkContext` |  | nvarchar(4000) | Y |  |
| `readwatermarkAttribute` |  | nvarchar(300) | Y |  |
| `imageWatermarks` |  | nvarchar(2000) | Y |  |
| `fromType` |  | nchar(10) | Y |  |
| `type` |  | nvarchar(20) | Y |  |

### 前綴 `Ind` — —（2 表）


#### `IndustryCategory` — （無中文名）　(列數約 7)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | Y |  |
| `createdTime` |  | datetime | Y |  |
| `creatorOID` |  | nchar(32) | Y |  |
| `updatedTime` |  | datetime | Y |  |
| `updaterOID` |  | nchar(32) | Y |  |
| `id` |  | nvarchar(100) | Y |  |
| `name` |  | nvarchar(100) | Y |  |
| `nameKey` |  | nvarchar(100) | Y |  |

#### `IndicatorDefinition` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `indicatorId` |  | nvarchar(100) | N |  |
| `indicatorDescription` |  | nvarchar(300) | Y |  |
| `workSiteId` |  | nvarchar(100) | N |  |
| `userName` |  | nvarchar(100) | N |  |
| `password` |  | nvarchar(100) | N |  |
| `processIds` |  | nvarchar(300) | N |  |
| `processNames` |  | nvarchar(300) | N |  |
| `dbCfgId` |  | nvarchar(100) | Y |  |
| `sqlClause` |  | nvarchar(2000) | Y |  |
| `indicatorCalculationType` |  | int | N |  |
| `calculationIntervalType` |  | int | N |  |
| `calculationStandardType` |  | int | N |  |
| `isPercent` |  | int | N |  |
| `companyId` |  | nvarchar(100) | Y |  |
| `product` |  | nvarchar(50) | Y |  |
| `startDate` |  | datetime | N |  |
| `latelyDate` |  | datetime | Y |  |
| `nextDate` |  | datetime | N |  |
| `latelyResult` |  | real | Y |  |
| `createdTime` |  | datetime | N |  |
| `creatorOID` |  | nchar(32) | N |  |
| `updateTime` |  | datetime | N |  |
| `updaterOID` |  | nchar(32) | N |  |

### 前綴 `Dat` — —（1 表）


#### `DataAccessDefinition` — （無中文名）　(列數約 7)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `containerOID` |  | nchar(32) | Y |  |
| `dataAccessName` |  | nvarchar(100) | N |  |
| `id` |  | nvarchar(100) | N |  |
| `dataBaseName` |  | nvarchar(100) | Y |  |
| `dataBaseType` |  | nvarchar(50) | Y |  |
| `hostName` |  | nvarchar(250) | Y |  |
| `oracleServiceName` |  | nvarchar(50) | Y |  |
| `password` |  | nvarchar(50) | Y |  |
| `portNumber` |  | int | Y |  |
| `userAccount` |  | nvarchar(50) | Y |  |
| `connectionProperty` |  | ntext | Y |  |
| `status` |  | varchar(30) | Y |  |

### 前綴 `Ana` — —（2 表）


#### `AnalyzedServiceParameter` — （無中文名）　(列數約 4)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `parameterIndex` |  | int | N |  |
| `dataType` |  | nvarchar(10) | N |  |
| `id` |  | nvarchar(100) | N |  |
| `name` |  | nvarchar(100) | N |  |
| `parameterMode` |  | nvarchar(10) | N |  |
| `length` |  | int | Y |  |
| `initialValue` |  | nvarchar(1000) | Y |  |
| `description` |  | ntext | N |  |
| `containerOID` |  | nchar(32) | N |  |

#### `AnalyzedService` — （無中文名）　(列數約 2)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `id` |  | nvarchar(100) | N |  |
| `name` |  | nvarchar(100) | N |  |
| `description` |  | ntext | N |  |
| `serverType` |  | nvarchar(50) | N |  |
| `serverIp` |  | nvarchar(50) | N |  |
| `serverPort` |  | nvarchar(10) | N |  |
| `jndiName` |  | nvarchar(50) | N |  |
| `methodName` |  | nvarchar(50) | N |  |
| `homeClassName` |  | nvarchar(100) | N |  |

### 前綴 `Sub` — —（2 表）


#### `SubFlow` — （無中文名）　(列數約 5)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `containerOID` |  | nchar(32) | Y |  |
| `subFlowDefinitionId` |  | nvarchar(100) | N |  |
| `objectVersion` |  | int | N |  |
| `executionType` |  | nvarchar(50) | N |  |
| `subFlowIndex` |  | int | N |  |

#### `SubFlowActivityInstance` — （無中文名）　(列數約 1)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `containerOID` |  | nchar(32) | N |  |
| `contextOID` |  | nchar(32) | N |  |
| `currentState` |  | int | N |  |
| `terminateReason` |  | int | Y |  |
| `definitionId` |  | nvarchar(100) | N |  |
| `comeBackActivityInstOID` |  | nchar(32) | Y |  |
| `objectVersion` |  | int | N |  |
| `createdTime` |  | datetime | N |  |
| `container1OID` |  | nchar(32) | Y |  |
| `container2OID` |  | nchar(32) | Y |  |
| `redoRefActivityInstOID` |  | nchar(32) | Y |  |

### 前綴 `dfD` — —（1 表）


#### `dfDocChange` — （無中文名）　(列數約 5)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `txtSerialNo` |  | nvarchar(255) | Y |  |
| `txtChageDocNo` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `chkMemo` |  | nvarchar(255) | Y |  |
| `HT10` |  | nvarchar(255) | Y |  |
| `chkMemo_txt` |  | nvarchar(255) | Y |  |
| `chkDept` |  | nvarchar(255) | Y |  |
| `validateDate` |  | datetime | Y |  |
| `txtMemo` |  | nvarchar(255) | Y |  |
| `txtNewVersion` |  | nvarchar(255) | Y |  |
| `RadApplyItem` |  | nvarchar(255) | Y |  |
| `txtOldversion` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `TextBox17` |  | nvarchar(255) | Y |  |
| `txtChange` |  | nvarchar(255) | Y |  |
| `txtDocName` |  | nvarchar(255) | Y |  |
| `HT1` |  | nvarchar(255) | Y |  |
| `HT3` |  | nvarchar(255) | Y |  |
| `HT2` |  | nvarchar(255) | Y |  |
| `HT5` |  | nvarchar(255) | Y |  |
| `HT4` |  | nvarchar(255) | Y |  |
| `HT7` |  | nvarchar(255) | Y |  |
| `HT6` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `HT9` |  | nvarchar(255) | Y |  |
| `HT8` |  | nvarchar(255) | Y |  |
| `DateApply` |  | datetime | Y |  |
| `txtApplyperpos` |  | nvarchar(255) | Y |  |
| `txtUnit` |  | nvarchar(255) | Y |  |
| `stopDate` |  | datetime | Y |  |
| `DialogInputLabel16` |  | nvarchar(255) | Y |  |
| `DIL1` |  | nvarchar(255) | Y |  |
| `RadDocLevel` |  | nvarchar(255) | Y |  |
| `TextBox49` |  | nvarchar(255) | Y |  |

### 前綴 `Gua` — —（3 表）


#### `GuardServiceExceptionRecord` — （無中文名）　(列數約 2)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `exceptionTime` |  | datetime | N |  |
| `exceptionStatus` |  | int | N |  |
| `referToGSRegOID` |  | nchar(32) | N |  |
| `causesOfException` |  | int | N |  |

#### `GuardServiceReg` — （無中文名）　(列數約 1)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | Y |  |
| `wfServerId` |  | nvarchar(50) | N |  |
| `guardServiceInfo` |  | ntext | N |  |
| `hardwareKey` |  | ntext | N |  |

#### `GuardServiseServer` — （無中文名）　(列數約 1)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | Y |  |
| `serverAddress` |  | nvarchar(50) | N |  |
| `serverPort` |  | nvarchar(10) | N |  |
| `macAddress` |  | nvarchar(50) | Y |  |

### 前綴 `Upg` — —（1 表）


#### `UpgradeRecord` — （無中文名）　(列數約 4)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `fileName` |  | nvarchar(1000) | N |  |
| `sqlCommand` |  | nvarchar(4000) | N |  |
| `action_result` |  | char(1) | Y |  |
| `action_messages` |  | nvarchar(500) | Y |  |

### 前綴 `dfn` — —（1 表）


#### `dfntrequest` — （無中文名）　(列數約 4)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `DT1` |  | datetime | Y |  |
| `RB1` |  | nvarchar(255) | Y |  |
| `DT3` |  | datetime | Y |  |
| `RB3` |  | nvarchar(255) | Y |  |
| `TB1` |  | nvarchar(255) | Y |  |
| `DT2` |  | datetime | Y |  |
| `RB2` |  | nvarchar(255) | Y |  |
| `HT1` |  | nvarchar(255) | Y |  |
| `TB3` |  | nvarchar(255) | Y |  |
| `RB4` |  | nvarchar(255) | Y |  |
| `TA1` |  | nvarchar(255) | Y |  |
| `TB2` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `HT3` |  | nvarchar(255) | Y |  |
| `TB5` |  | int | Y |  |
| `HT2` |  | nvarchar(255) | Y |  |
| `TB4` |  | nvarchar(255) | Y |  |
| `TB7` |  | nvarchar(255) | Y |  |
| `TB6` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `formSerialNumber` |  | nvarchar(255) | Y |  |

### 前綴 `Prs` — —（1 表）


#### `PrsInsLvl` — （無中文名）　(列數約 3)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `lvlValue` |  | int | N |  |
| `lvlName` |  | nvarchar(100) | N |  |
| `description` |  | nvarchar(1000) | Y |  |
| `bundleContainer` |  | ntext | Y |  |

### 前綴 `dfo` — —（1 表）


#### `dfotinspection` — （無中文名）　(列數約 3)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `PD5` |  | nvarchar(255) | Y |  |
| `PD4` |  | nvarchar(255) | Y |  |
| `PD7` |  | nvarchar(255) | Y |  |
| `TB1` |  | nvarchar(255) | Y |  |
| `PD6` |  | nvarchar(255) | Y |  |
| `PD9` |  | nvarchar(255) | Y |  |
| `TB3` |  | nvarchar(255) | Y |  |
| `PD8` |  | nvarchar(255) | Y |  |
| `TB2` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `TB5` |  | nvarchar(255) | Y |  |
| `TB4` |  | nvarchar(255) | Y |  |
| `TB7` |  | nvarchar(255) | Y |  |
| `TB6` |  | nvarchar(255) | Y |  |
| `TB9` |  | nvarchar(255) | Y |  |
| `TB8` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `DT1` |  | datetime | Y |  |
| `DT3` |  | datetime | Y |  |
| `DT2` |  | datetime | Y |  |
| `DT5` |  | datetime | Y |  |
| `TA2` |  | nvarchar(255) | Y |  |
| `DT4` |  | datetime | Y |  |
| `TA1` |  | nvarchar(255) | Y |  |
| `DT6` |  | datetime | Y |  |
| `TB12` |  | nvarchar(255) | Y |  |
| `TB11` |  | nvarchar(255) | Y |  |
| `TB10` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `PD10` |  | nvarchar(255) | Y |  |
| `SN1` |  | nvarchar(255) | Y |  |
| `TB13` |  | nvarchar(255) | Y |  |
| `PD1` |  | nvarchar(255) | Y |  |
| `PD3` |  | nvarchar(255) | Y |  |
| `PD2` |  | nvarchar(255) | Y |  |

### 前綴 `cus` — —（2 表）


#### `custAttachedFilesToForm` — （無中文名）　(列數約 2)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `serverType` |  | nvarchar(10) | N | PK |
| `serverID` |  | nvarchar(20) | N | PK |
| `serverIP` |  | nvarchar(15) | N |  |
| `serverLoginID` |  | nvarchar(50) | Y |  |
| `serverLoginPassword` |  | nvarchar(50) | Y |  |
| `getSpecFiles` |  | int | N |  |

#### `custRestfulAuthInfo` — （無中文名）　(列數約 1)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `tokenURL` |  | nvarchar(255) | N |  |
| `clientId` |  | nvarchar(255) | N |  |
| `clientSecret` |  | nvarchar(255) | N |  |
| `userName` |  | nvarchar(255) | N |  |
| `password` |  | nvarchar(255) | N |  |
| `authKey` |  | nvarchar(255) | N |  |
| `description` |  | nvarchar(255) | Y |  |

### 前綴 `Wiz` — —（1 表）


#### `WizardAuthority` — （無中文名）　(列數約 3)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `groupList` |  | ntext | Y |  |
| `userList` |  | ntext | Y |  |
| `organizationUnitList` |  | ntext | Y |  |
| `wizardType` |  | nvarchar(100) | N |  |

### 前綴 `Cuz` — —（4 表）


#### `CuzModuleDefinition` — （無中文名）　(列數約 2)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N |  |
| `objectVersion` |  | int | N |  |
| `id` |  | char(45) | N | PK |
| `name` |  | nvarchar(100) | N |  |
| `isDefault` |  | int | N |  |
| `bundleContainer` |  | ntext | Y |  |
| `containerID` |  | char(45) | N |  |

#### `CuzPatternDefinition` — （無中文名）　(列數約 1)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N |  |
| `objectVersion` |  | int | N |  |
| `id` |  | char(45) | N | PK |
| `name` |  | nvarchar(100) | N |  |
| `isDefault` |  | int | N |  |
| `bundleContainer` |  | ntext | Y |  |
| `ownerOID` |  | nchar(32) | Y |  |

#### `CuzProgramDefinition` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N |  |
| `objectVersion` |  | int | N |  |
| `id` |  | char(45) | N | PK |
| `name` |  | nvarchar(100) | N |  |
| `linkUrl` |  | nvarchar(255) | N |  |
| `isDefault` |  | int | N |  |
| `bundleContainer` |  | ntext | Y |  |
| `containerID` |  | char(45) | N |  |
| `urlType` |  | int | N |  |
| `ownerOID` |  | nchar(32) | N |  |

#### `CuzProgramRefProcess` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N |  |
| `objectVersion` |  | int | N |  |
| `id` |  | nvarchar(100) | N | PK |
| `cuzProgramId` |  | char(45) | N |  |
| `processId` |  | nvarchar(100) | N |  |
| `bundleContainer` |  | ntext | Y |  |

### 前綴 `Api` — —（1 表）


#### `ApiParameters` — （無中文名）　(列數約 3)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `apiKey` |  | varchar(100) | Y |  |
| `apiValue` |  | varchar(500) | Y |  |

### 前綴 `dfm` — —（1 表）


#### `dfmagsug` — （無中文名）　(列數約 3)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `hdndfsug_kindname` |  | nvarchar(255) | Y |  |
| `dfsug_desc` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `dfsug_user` |  | nvarchar(255) | Y |  |
| `dfsug_no` |  | nvarchar(255) | Y |  |
| `dfsug_advise` |  | nvarchar(255) | Y |  |
| `dfsug_hdn_username` |  | nvarchar(255) | Y |  |
| `dfsug_hdn_edesc` |  | nvarchar(255) | Y |  |
| `hdndfsug_bossname` |  | nvarchar(255) | Y |  |
| `hdnchkfinance` |  | nvarchar(255) | Y |  |
| `dfsug_apdate` |  | nvarchar(255) | Y |  |
| `dfsug_title` |  | nvarchar(255) | Y |  |
| `dfsug_hdn_deptcode` |  | nvarchar(255) | Y |  |
| `hdndfsug_deptoid` |  | nvarchar(255) | Y |  |
| `dfsug_kind` |  | nvarchar(255) | Y |  |
| `hdnchkchairman` |  | nvarchar(255) | Y |  |
| `dfsug_deptname` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `hdndfsug_bosscode` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |

### 前綴 `Oau` — —（2 表）


#### `OauthSetting` — （無中文名）　(列數約 3)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `id` |  | nvarchar(100) | Y |  |
| `name` |  | nvarchar(100) | Y |  |
| `appId` |  | nvarchar(100) | Y |  |
| `appSecret` |  | nvarchar(1000) | Y |  |
| `callBackUrl` |  | nvarchar(1000) | Y |  |
| `logoImg` |  | ntext | Y |  |
| `isEnable` |  | int | Y |  |
| `oauthOrder` |  | int | Y |  |
| `authData` |  | nvarchar(4000) | Y |  |
| `userInfoData` |  | nvarchar(4000) | Y |  |
| `isDefault` |  | int | Y |  |

#### `OauthAuthentication` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `userOID` |  | nchar(32) | Y |  |
| `userId` |  | nvarchar(100) | Y |  |
| `prod` |  | nvarchar(100) | Y |  |
| `uuid` |  | nvarchar(1000) | Y |  |
| `updateTime` |  | datetime | Y |  |

### 前綴 `Ext` — —（3 表）


#### `ExternalService` — （無中文名）　(列數約 2)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `product` |  | nvarchar(50) | N |  |
| `serviceType` |  | nvarchar(20) | N |  |
| `id` |  | nvarchar(100) | N |  |
| `name` |  | nvarchar(100) | N |  |
| `description` |  | ntext | N |  |

#### `ExternalPackage` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `href` |  | nvarchar(100) | N |  |
| `objectVersion` |  | int | N |  |
| `containerOID` |  | nchar(32) | N |  |

#### `ExternalReference` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `location` |  | nvarchar(100) | N |  |
| `namespace` |  | nvarchar(100) | Y |  |
| `objectVersion` |  | int | N |  |
| `xref` |  | nvarchar(100) | Y |  |

### 前綴 `Com` — —（2 表）


#### `CombinationService` — （無中文名）　(列數約 2)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `productId` |  | nvarchar(50) | N |  |
| `externalServiceId` |  | nvarchar(100) | N |  |
| `analyzedServiceId` |  | nvarchar(100) | N |  |
| `combinationServiceId` |  | nvarchar(100) | N |  |

#### `CompositeType` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `parentOID` |  | nchar(32) | Y |  |
| `relevantDataId` |  | nvarchar(50) | Y |  |
| `typeName` |  | nvarchar(50) | Y |  |
| `namespaceURI` |  | nvarchar(255) | Y |  |

### 前綴 `axm` — —（2 表）


#### `axmt410` — （無中文名）　(列數約 1)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `oea21` |  | nvarchar(255) | Y |  |
| `oea211` |  | nvarchar(255) | Y |  |
| `oea65` |  | nvarchar(255) | Y |  |
| `oea63` |  | nvarchar(255) | Y |  |
| `oea26` |  | nvarchar(255) | Y |  |
| `oea25` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `oea24` |  | nvarchar(255) | Y |  |
| `oea23` |  | nvarchar(255) | Y |  |
| `gen02` |  | nvarchar(255) | Y |  |
| `oea62` |  | nvarchar(255) | Y |  |
| `oea61` |  | nvarchar(255) | Y |  |
| `oea212` |  | nvarchar(255) | Y |  |
| `oea213` |  | nvarchar(255) | Y |  |
| `oag02_2` |  | nvarchar(255) | Y |  |
| `oah02` |  | nvarchar(255) | Y |  |
| `oag02_1` |  | nvarchar(255) | Y |  |
| `oea17_ds` |  | nvarchar(255) | Y |  |
| `oeaud06` |  | nvarchar(255) | Y |  |
| `oab02` |  | nvarchar(255) | Y |  |
| `occ02` |  | nvarchar(255) | Y |  |
| `oea33` |  | nvarchar(255) | Y |  |
| `oea32` |  | nvarchar(255) | Y |  |
| `oea31` |  | nvarchar(255) | Y |  |
| `oea044` |  | nvarchar(255) | Y |  |
| `oea162` |  | nvarchar(255) | Y |  |
| `oea37` |  | nvarchar(255) | Y |  |
| `oea163` |  | nvarchar(255) | Y |  |
| `oea161` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `ofs02` |  | nvarchar(255) | Y |  |
| `oea1004` |  | nvarchar(255) | Y |  |
| `oea1015_occ02` |  | nvarchar(255) | Y |  |
| `occ02_a` |  | nvarchar(255) | Y |  |
| `oeahold` |  | nvarchar(255) | Y |  |
| `oea00` |  | nvarchar(255) | Y |  |
| `oea44` |  | nvarchar(255) | Y |  |
| `oea43` |  | nvarchar(255) | Y |  |
| `oea032` |  | nvarchar(255) | Y |  |
| `oea42` |  | nvarchar(255) | Y |  |
| `oea41` |  | nvarchar(255) | Y |  |
| `oea04` |  | nvarchar(255) | Y |  |
| `oea48` |  | nvarchar(255) | Y |  |
| `oea03` |  | nvarchar(255) | Y |  |
| `oea47` |  | nvarchar(255) | Y |  |
| `oea02` |  | nvarchar(255) | Y |  |
| `oea46` |  | nvarchar(255) | Y |  |
| `oea01` |  | nvarchar(255) | Y |  |
| `oea80` |  | nvarchar(255) | Y |  |
| `oaydesc` |  | nvarchar(255) | Y |  |
| `gem02` |  | nvarchar(255) | Y |  |
| `oea81` |  | nvarchar(255) | Y |  |
| `oab02_2` |  | nvarchar(255) | Y |  |
| `oak02` |  | nvarchar(255) | Y |  |
| `pmc03` |  | nvarchar(255) | Y |  |
| `oea1015` |  | nvarchar(255) | Y |  |
| `oea08` |  | nvarchar(255) | Y |  |
| `oea07` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `oac02` |  | nvarchar(255) | Y |  |
| `oea06` |  | nvarchar(255) | Y |  |
| `oea05` |  | nvarchar(255) | Y |  |
| `oag02` |  | nvarchar(255) | Y |  |
| `oea09` |  | nvarchar(255) | Y |  |
| `oea11` |  | nvarchar(255) | Y |  |
| `oea10` |  | nvarchar(255) | Y |  |
| `oap042` |  | nvarchar(255) | Y |  |
| `oea15` |  | nvarchar(255) | Y |  |
| `oac02_2` |  | nvarchar(255) | Y |  |
| `oap043` |  | nvarchar(255) | Y |  |
| `oea14` |  | nvarchar(255) | Y |  |
| `oap044` |  | nvarchar(255) | Y |  |
| `oap045` |  | nvarchar(255) | Y |  |
| `oea12` |  | nvarchar(255) | Y |  |
| `oea50` |  | nvarchar(255) | Y |  |
| `oea18` |  | nvarchar(255) | Y |  |
| `oea17` |  | nvarchar(255) | Y |  |
| `oap041` |  | nvarchar(255) | Y |  |

#### `axmt410_s_oeb` — （無中文名）　(列數約 1)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `oeb14t` |  | nvarchar(255) | Y |  |
| `oeb03` |  | nvarchar(255) | Y |  |
| `oeb14` |  | nvarchar(255) | Y |  |
| `oeb13` |  | nvarchar(255) | Y |  |
| `oeb24` |  | nvarchar(255) | Y |  |
| `oeb12` |  | nvarchar(255) | Y |  |
| `ima021` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `oeb70` |  | nvarchar(255) | Y |  |
| `oeb908` |  | nvarchar(255) | Y |  |
| `oeb06` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `oeb05` |  | nvarchar(255) | Y |  |
| `ima15` |  | nvarchar(255) | Y |  |
| `oeb04` |  | nvarchar(255) | Y |  |
| `oeb15` |  | nvarchar(255) | Y |  |
| `oeb19` |  | nvarchar(255) | Y |  |

### 前綴 `HIL` — —（1 表）


#### `HILOSEQUENCES` — （無中文名）　(列數約 1)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `SEQUENCENAME` |  | varchar(50) | N | PK |
| `HIGHVALUES` |  | int | N |  |

### 前綴 `Tip` — —（1 表）


#### `TiptopModel` — （無中文名）　(列數約 1)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | char(32) | N | PK |
| `id` |  | nvarchar(50) | N |  |
| `description` |  | ntext | Y |  |
| `mappingSet` |  | ntext | Y |  |
| `appOIDList` |  | ntext | Y |  |
| `wsdlSet` |  | ntext | Y |  |
| `workflowServerID` |  | nvarchar(50) | Y |  |
| `tiptopServerUserID` |  | ntext | Y |  |
| `tiptopServerIP` |  | ntext | Y |  |
| `templateFieldAccessDefMap` |  | ntext | Y |  |
| `modelConfig` |  | ntext | Y |  |
| `memoConfig` |  | ntext | Y |  |

### 前綴 `ESS` — —（1 表）


#### `ESSF26` — （無中文名）　(列數約 1)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `ESSJC019` |  | nvarchar(255) | Y |  |
| `ESSJC017` |  | nvarchar(255) | Y |  |
| `ESSJC018` |  | nvarchar(255) | Y |  |
| `CREATOR` |  | nvarchar(255) | Y |  |
| `ESSJC011` |  | nvarchar(255) | Y |  |
| `ESSJC012` |  | nvarchar(255) | Y |  |
| `ESSJC010` |  | nvarchar(255) | Y |  |
| `ESSJC015` |  | nvarchar(255) | Y |  |
| `ESSJC016` |  | nvarchar(255) | Y |  |
| `ESSJC013` |  | nvarchar(255) | Y |  |
| `ESSJC014` |  | nvarchar(255) | Y |  |
| `MODIFIER` |  | nvarchar(255) | Y |  |
| `ESSJC040` |  | nvarchar(255) | Y |  |
| `ESSJC041` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `COMPANY` |  | nvarchar(255) | Y |  |
| `ESSJC008` |  | nvarchar(255) | Y |  |
| `ESSJC009` |  | nvarchar(255) | Y |  |
| `CREATE_DATE` |  | nvarchar(255) | Y |  |
| `ESSJC006` |  | nvarchar(255) | Y |  |
| `ESSJC007` |  | nvarchar(255) | Y |  |
| `ESSJC044` |  | nvarchar(255) | Y |  |
| `ESSJC001` |  | nvarchar(255) | Y |  |
| `ESSJC042` |  | nvarchar(255) | Y |  |
| `ESSJC043` |  | nvarchar(255) | Y |  |
| `ESSJC004` |  | nvarchar(255) | Y |  |
| `ESSJC005` |  | nvarchar(255) | Y |  |
| `ESSJC002` |  | nvarchar(255) | Y |  |
| `ESSJC003` |  | nvarchar(255) | Y |  |
| `ESSJC030` |  | nvarchar(255) | Y |  |
| `FLAG` |  | nvarchar(255) | Y |  |
| `ESSJC039` |  | nvarchar(255) | Y |  |
| `ESSJC033` |  | nvarchar(255) | Y |  |
| `ESSJC034` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `ESSJC031` |  | nvarchar(255) | Y |  |
| `ESSJC032` |  | nvarchar(255) | Y |  |
| `ESSJC037` |  | nvarchar(255) | Y |  |
| `ESSJC038` |  | nvarchar(255) | Y |  |
| `ESSJC035` |  | nvarchar(255) | Y |  |
| `ESSJC036` |  | nvarchar(255) | Y |  |
| `MODI_DATE` |  | nvarchar(255) | Y |  |
| `PL_RowType` |  | nvarchar(255) | Y |  |
| `USR_GROUP` |  | nvarchar(255) | Y |  |
| `ESSJC028` |  | nvarchar(255) | Y |  |
| `ESSJC029` |  | nvarchar(255) | Y |  |
| `ESSJC022` |  | nvarchar(255) | Y |  |
| `ESSJC023` |  | nvarchar(255) | Y |  |
| `ESSJC020` |  | nvarchar(255) | Y |  |
| `ESSJC021` |  | nvarchar(255) | Y |  |
| `ESSJC026` |  | nvarchar(255) | Y |  |
| `ESSJC027` |  | nvarchar(255) | Y |  |
| `ESSJC024` |  | nvarchar(255) | Y |  |
| `ESSJC025` |  | nvarchar(255) | Y |  |

### 前綴 `dfM` — —（1 表）


#### `dfMarketing` — （無中文名）　(列數約 1)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `RB1` |  | nvarchar(255) | Y |  |
| `RB3` |  | nvarchar(255) | Y |  |
| `TB1` |  | nvarchar(255) | Y |  |
| `RB2` |  | nvarchar(255) | Y |  |
| `RB12_txt` |  | nvarchar(255) | Y |  |
| `RB5` |  | nvarchar(255) | Y |  |
| `TB3` |  | nvarchar(255) | Y |  |
| `RB4` |  | nvarchar(255) | Y |  |
| `TB2` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `RB7` |  | nvarchar(255) | Y |  |
| `TB5` |  | nvarchar(255) | Y |  |
| `RB6` |  | nvarchar(255) | Y |  |
| `TB4` |  | nvarchar(255) | Y |  |
| `RB9` |  | nvarchar(255) | Y |  |
| `TB7` |  | nvarchar(255) | Y |  |
| `RB8` |  | nvarchar(255) | Y |  |
| `TB6` |  | nvarchar(255) | Y |  |
| `DIL1` |  | nvarchar(255) | Y |  |
| `TB9` |  | nvarchar(255) | Y |  |
| `DIL2` |  | nvarchar(255) | Y |  |
| `TB8` |  | nvarchar(255) | Y |  |
| `DT10` |  | datetime | Y |  |
| `RB9_txt` |  | nvarchar(255) | Y |  |
| `RB13_txt` |  | nvarchar(255) | Y |  |
| `CB11` |  | nvarchar(255) | Y |  |
| `DT1` |  | datetime | Y |  |
| `CB10` |  | nvarchar(255) | Y |  |
| `DT3` |  | datetime | Y |  |
| `DT2` |  | datetime | Y |  |
| `DT5` |  | datetime | Y |  |
| `HT1` |  | nvarchar(255) | Y |  |
| `DT4` |  | datetime | Y |  |
| `DT7` |  | datetime | Y |  |
| `HT3` |  | nvarchar(255) | Y |  |
| `RB14_txt` |  | nvarchar(255) | Y |  |
| `DT6` |  | datetime | Y |  |
| `HT2` |  | nvarchar(255) | Y |  |
| `DT9` |  | datetime | Y |  |
| `HT5` |  | nvarchar(255) | Y |  |
| `TB12` |  | nvarchar(255) | Y |  |
| `DT8` |  | datetime | Y |  |
| `HT4` |  | nvarchar(255) | Y |  |
| `TB11` |  | nvarchar(255) | Y |  |
| `HT7` |  | nvarchar(255) | Y |  |
| `RB7_txt` |  | nvarchar(255) | Y |  |
| `TB10` |  | nvarchar(255) | Y |  |
| `HT6` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `HT8` |  | nvarchar(255) | Y |  |
| `CB2` |  | nvarchar(255) | Y |  |
| `TB18` |  | nvarchar(255) | Y |  |
| `CB1` |  | nvarchar(255) | Y |  |
| `TB17` |  | nvarchar(255) | Y |  |
| `CB4` |  | nvarchar(255) | Y |  |
| `TB16` |  | nvarchar(255) | Y |  |
| `CB3` |  | nvarchar(255) | Y |  |
| `TB15` |  | nvarchar(255) | Y |  |
| `CB6` |  | nvarchar(255) | Y |  |
| `TB14` |  | nvarchar(255) | Y |  |
| `CB5` |  | nvarchar(255) | Y |  |
| `TB13` |  | nvarchar(255) | Y |  |
| `CB8` |  | nvarchar(255) | Y |  |
| `CB7` |  | nvarchar(255) | Y |  |
| `CB9` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `CB15` |  | nvarchar(255) | Y |  |
| `CB14` |  | nvarchar(255) | Y |  |
| `CB13` |  | nvarchar(255) | Y |  |
| `CB12` |  | nvarchar(255) | Y |  |
| `TA2` |  | nvarchar(255) | Y |  |
| `TA1` |  | nvarchar(255) | Y |  |
| `TA4` |  | nvarchar(255) | Y |  |
| `TA3` |  | nvarchar(255) | Y |  |
| `TA13` |  | nvarchar(255) | Y |  |
| `TA6` |  | nvarchar(255) | Y |  |
| `RB10` |  | nvarchar(255) | Y |  |
| `TA12` |  | nvarchar(255) | Y |  |
| `TA5` |  | nvarchar(255) | Y |  |
| `RB10_txt` |  | nvarchar(255) | Y |  |
| `TA11` |  | nvarchar(255) | Y |  |
| `TA8` |  | nvarchar(255) | Y |  |
| `TA10` |  | nvarchar(255) | Y |  |
| `TA7` |  | nvarchar(255) | Y |  |
| `TA9` |  | nvarchar(255) | Y |  |
| `RB13` |  | nvarchar(255) | Y |  |
| `RB14` |  | nvarchar(255) | Y |  |
| `TA16` |  | nvarchar(255) | Y |  |
| `RB11` |  | nvarchar(255) | Y |  |
| `TA15` |  | nvarchar(255) | Y |  |
| `RB12` |  | nvarchar(255) | Y |  |
| `TA14` |  | nvarchar(255) | Y |  |
| `RB11_txt` |  | nvarchar(255) | Y |  |

### 前綴 `dfA` — —（1 表）


#### `dfActivity` — （無中文名）　(列數約 1)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `TA2` |  | nvarchar(255) | Y |  |
| `TA1` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `TA4` |  | nvarchar(255) | Y |  |
| `TA3` |  | nvarchar(255) | Y |  |
| `TA6` |  | nvarchar(255) | Y |  |
| `TA5` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `DIL1` |  | nvarchar(255) | Y |  |
| `DIL2` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |

### 前綴 `SnG` — —（1 表）


#### `SnGenRule` — （無中文名）　(列數約 1)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `snId` |  | nvarchar(100) | N |  |
| `snName` |  | nvarchar(100) | N |  |
| `description` |  | ntext | Y |  |
| `snDigit` |  | int | N |  |
| `snSample` |  | nvarchar(100) | Y |  |
| `rulesString` |  | ntext | N |  |

### 前綴 `Pat` — —（1 表）


#### `PatternDefinition` — （無中文名）　(列數約 1)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N |  |
| `objectVersion` |  | int | N |  |
| `id` |  | nvarchar(50) | N | PK |
| `name` |  | nvarchar(100) | N |  |
| `isDefault` |  | int | N |  |
| `bundleContainer` |  | ntext | Y |  |

### 前綴 `TFA` — —（4 表）


#### `TFASetting` — （無中文名）　(列數約 1)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `appName` |  | nvarchar(100) | Y |  |
| `enableSet` |  | int | N |  |
| `verifyType` |  | int | N |  |
| `validDay` |  | int | N |  |
| `jndiName` |  | nvarchar(2000) | Y |  |
| `validMode` |  | int | Y |  |
| `intergrationPara` |  | nvarchar(2000) | Y |  |
| `allowIpSet` |  | int | N |  |
| `checkBindIdExpert` |  | int | N |  |
| `adminAccount` |  | nvarchar(100) | Y |  |
| `adminPassword` |  | nvarchar(100) | Y |  |

#### `TFANotVerifylist` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `userOID` |  | nchar(32) | N | PK |
| `userId` |  | nvarchar(100) | N |  |
| `userName` |  | nvarchar(100) | N |  |

#### `TFATrustDevice` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `userOID` |  | nchar(32) | N |  |
| `deviceId` |  | nvarchar(2000) | Y |  |
| `clientIP` |  | nvarchar(100) | Y |  |
| `deviceinfo` |  | nvarchar(2000) | Y |  |
| `updateTime` |  | datetime | N |  |
| `endTime` |  | datetime | N |  |

#### `TFAuthentication` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `userOID` |  | nchar(32) | N |  |
| `verifyType` |  | int | N |  |
| `verifyKey` |  | nvarchar(100) | Y |  |
| `validMode` |  | int | N |  |

### 前綴 `Sma` — —（1 表）


#### `SmartEmployees` — （無中文名）　(列數約 1)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `imgBase64` |  | ntext | Y |  |
| `plugName` |  | nvarchar(256) | Y |  |
| `description` |  | nvarchar(256) | Y |  |
| `enableUrl` |  | nvarchar(256) | Y |  |
| `objectVersion` |  | int | Y |  |
| `createdTime` |  | datetime | Y |  |
| `creatorOID` |  | nvarchar(32) | Y |  |
| `updatedTime` |  | datetime | Y |  |
| `updaterOID` |  | nvarchar(32) | Y |  |

### 前綴 `CmD` — —（1 表）


#### `CmDocument` — （無中文名）　(列數約 1)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `createdTime` |  | datetime | N |  |
| `extentionName` |  | nvarchar(50) | Y |  |
| `logicalName` |  | nvarchar(100) | N |  |
| `physicalName` |  | nvarchar(255) | N |  |
| `version` |  | nvarchar(10) | N |  |
| `creatorOID` |  | nchar(32) | N |  |
| `containerOID` |  | nchar(32) | N |  |
| `description` |  | ntext | Y |  |

### 前綴 `Crm` — —（1 表）


#### `CrmModel` — （無中文名）　(列數約 1)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | char(32) | N | PK |
| `id` |  | nvarchar(50) | N |  |
| `description` |  | ntext | Y |  |
| `mappingSet` |  | ntext | Y |  |
| `appOIDList` |  | ntext | Y |  |
| `wsdlSet` |  | ntext | Y |  |
| `workflowServerID` |  | nvarchar(50) | Y |  |
| `crmServerUserID` |  | ntext | Y |  |
| `crmServerIP` |  | ntext | Y |  |
| `templateFieldAccessDefMap` |  | ntext | Y |  |
| `modelConfig` |  | ntext | Y |  |
| `memoConfig` |  | ntext | Y |  |

### 前綴 `All` — —（1 表）


#### `AllUserUnit` — （無中文名）　(列數約 1)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `id` |  | nvarchar(100) | N |  |
| `userName` |  | nvarchar(100) | N |  |

### 前綴 `Obj` — —（1 表）


#### `ObjectIdentity` — （無中文名）　(列數約 1)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `prefixValue` |  | char(17) | N |  |
| `h_highValue` |  | char(2) | N |  |
| `objectVersion` |  | int | N |  |
| `l_highValue` |  | char(9) | N |  |

### 前綴 `dfR` — —（1 表）


#### `dfResignation_10` — （無中文名）　(列數約 1)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `DT1` |  | datetime | Y |  |
| `RD3` |  | nvarchar(255) | Y |  |
| `RD2` |  | nvarchar(255) | Y |  |
| `TB1` |  | nvarchar(255) | Y |  |
| `DT2` |  | datetime | Y |  |
| `HT1` |  | nvarchar(255) | Y |  |
| `TA2` |  | nvarchar(255) | Y |  |
| `TB3` |  | nvarchar(255) | Y |  |
| `TA1` |  | nvarchar(255) | Y |  |
| `TB2` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `TB5` |  | nvarchar(255) | Y |  |
| `TA3` |  | nvarchar(255) | Y |  |
| `TB4` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `CB2` |  | nvarchar(255) | Y |  |
| `CB1` |  | nvarchar(255) | Y |  |
| `CB4` |  | nvarchar(255) | Y |  |
| `CB3` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `RD1` |  | nvarchar(255) | Y |  |

### 前綴 `Lab` — —（1 表）


#### `Labels` — （無中文名）　(列數約 1)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `id` |  | nvarchar(100) | N |  |
| `name` |  | ntext | Y |  |
| `type` |  | int | N |  |
| `ownerOID` |  | nchar(32) | Y |  |
| `description` |  | ntext | Y |  |

### 前綴 `Sec` — —（2 表）


#### `SecudocxSetting` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `id` |  | nvarchar(255) | Y |  |
| `isEnable` |  | int | Y |  |
| `plfPath` |  | nvarchar(255) | Y |  |
| `createdTime` |  | datetime | Y |  |
| `updatedTime` |  | datetime | Y |  |

#### `SecurityLevel` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `id` |  | nvarchar(100) | N |  |
| `levelName` |  | nvarchar(100) | N |  |
| `levelValue` |  | int | N |  |
| `description` |  | nvarchar(2000) | Y |  |

### 前綴 `cge` — —（2 表）


#### `cgexpense` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `cgexp_payment` |  | nvarchar(255) | Y |  |
| `hdncgexp_username` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `cgexp_place` |  | nvarchar(255) | Y |  |
| `cgexp_date` |  | datetime | Y |  |
| `cgexp_user` |  | nvarchar(255) | Y |  |
| `hdncgexp_bosscode` |  | nvarchar(255) | Y |  |
| `cgexp_total` |  | float | Y |  |
| `hdncgexp_deptOID` |  | nvarchar(255) | Y |  |
| `hdncgexp_bossname` |  | nvarchar(255) | Y |  |
| `cgexp_money` |  | float | Y |  |
| `cgexp_item` |  | nvarchar(255) | Y |  |
| `cgexp_deptname` |  | nvarchar(255) | Y |  |
| `hdncgexp_deptcode` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `cgexp_memo` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `cgexp_apdate` |  | nvarchar(255) | Y |  |

#### `cgexpense_detail` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `cgexp_gdmemo` |  | nvarchar(255) | Y |  |
| `cgexp_gddate` |  | datetime | Y |  |
| `cgexp_gdpayment` |  | nvarchar(300) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `cgexp_gdplace` |  | nvarchar(255) | Y |  |
| `cgexp_gdmoney` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `dfexp_gdno` |  | nvarchar(255) | Y |  |
| `cgexp_gditem` |  | nvarchar(max) | Y |  |

### 前綴 `Ref` — —（3 表）


#### `RefBizModel` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `cmItemId` |  | nvarchar(100) | N |  |
| `cmItemClassName` |  | nvarchar(255) | N |  |
| `version` |  | int | Y |  |
| `containerOID` |  | nchar(32) | N |  |
| `instanceGenerationMode` |  | int | N |  |

#### `RefContainer_ProcessInst` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `ReferContainerOID` |  | nchar(32) | N | PK |
| `ProcessInstanceOID` |  | nchar(32) | N | PK |

#### `RefUserTask` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `taskId` |  | nvarchar(100) | N |  |
| `containerOID` |  | nchar(32) | N |  |

### 前綴 `Ada` — —（4 表）


#### `AdapterApp` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | char(32) | N |  |
| `objectVersion` |  | int | N |  |
| `appId` |  | nvarchar(128) | N |  |
| `appUri` |  | nvarchar(256) | N |  |
| `adapterConfigOID` |  | char(32) | N |  |

#### `AdapterConfig` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | char(32) | N |  |
| `objectVersion` |  | int | N |  |
| `clientId` |  | text | N |  |
| `clientSecret` |  | text | N |  |
| `alias` |  | nvarchar(128) | N |  |
| `adapterType` |  | int | N |  |
| `oauthUrl` |  | nvarchar(256) | N |  |
| `apiUrl` |  | nvarchar(256) | N |  |
| `urlParam` |  | text | N |  |
| `pushType` |  | int | N |  |
| `oauthType` |  | int | N |  |
| `pushParam` |  | text | N |  |
| `organizationOID` |  | nchar(32) | Y |  |

#### `AdapterDingtalkTodoTask` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `sourceId` |  | nvarchar(100) | Y |  |
| `taskStatus` |  | nvarchar(100) | Y |  |
| `executeService` |  | nvarchar(100) | Y |  |
| `createdTime` |  | datetime | Y |  |
| `userOID` |  | nchar(32) | Y |  |
| `processSerialNumber` |  | nvarchar(100) | Y |  |
| `subject` |  | ntext | Y |  |
| `processDefinitionName` |  | nvarchar(100) | Y |  |
| `multiUserMode` |  | nvarchar(50) | Y |  |
| `taskInfo` |  | ntext | Y |  |
| `requesterOID` |  | nchar(32) | Y |  |
| `workItemOID` |  | nchar(32) | Y |  |
| `workItemCreateTime` |  | datetime | Y |  |
| `errorMsg` |  | ntext | Y |  |
| `manualTime` |  | datetime | Y |  |

#### `AdapterUser` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | char(32) | N |  |
| `objectVersion` |  | int | N |  |
| `userOID` |  | char(32) | N |  |
| `adapterConfigOID` |  | char(32) | N |  |
| `oauthID` |  | nvarchar(64) | Y |  |
| `enable` |  | int | N |  |
| `lastLogin` |  | datetime | Y |  |
| `loginToken` |  | text | Y |  |
| `userInfo` |  | ntext | Y |  |

### 前綴 `TIM` — —（1 表）


#### `TIMERS` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `TIMERID` |  | varchar(80) | N | PK |
| `TARGETID` |  | varchar(250) | N | PK |
| `INITIALDATE` |  | datetime | N |  |
| `TIMERINTERVAL` |  | bigint | Y |  |
| `INSTANCEPK` |  | image | Y |  |
| `INFO` |  | image | Y |  |

### 前綴 `Xpr` — —（1 表）


#### `XpressionDefinition` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `containerOID` |  | nchar(32) | N |  |
| `objectVersion` |  | int | N |  |
| `content` |  | ntext | N |  |

### 前綴 `Exc` — —（2 表）


#### `ExceptionNotificationDef` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `numOfRedo` |  | int | N |  |
| `redoIntervalTime` |  | real | N |  |
| `redoIntervalTimeUnit` |  | nvarchar(50) | N |  |
| `containerOID` |  | nchar(32) | N |  |

#### `ExceptionRetryDef` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `numOfRedo` |  | int | N |  |
| `redoIntervalTime` |  | real | N |  |
| `redoIntervalTimeUnit` |  | nvarchar(50) | N |  |
| `containerOID` |  | nchar(32) | N |  |

### 前綴 `CmI` — —（2 表）


#### `CmItemAcsRight` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `rightType` |  | int | N |  |
| `ownerId` |  | nvarchar(100) | Y |  |
| `organizationId` |  | nvarchar(100) | Y |  |
| `categoryOID` |  | nchar(32) | N |  |

#### `CmItemCategory` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `cateId` |  | nvarchar(50) | N |  |
| `categoryName` |  | nvarchar(100) | N |  |
| `bundleContainer` |  | ntext | Y |  |

### 前綴 `Def` — —（4 表）


#### `DefAccessRight` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `id` |  | nvarchar(100) | N |  |
| `accessRightName` |  | nvarchar(100) | N |  |
| `description` |  | ntext | Y |  |
| `limitType` |  | int | Y |  |
| `limitContent` |  | nvarchar(500) | Y |  |

#### `DefCmItem` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `cmItemId` |  | nvarchar(100) | N |  |
| `chkOutUserOID` |  | nchar(32) | Y |  |
| `chkOutTime` |  | datetime | Y |  |
| `chkInTime` |  | datetime | Y |  |
| `lastVersion` |  | int | N |  |
| `pubStatus` |  | nvarchar(50) | N |  |
| `cmItemName` |  | nvarchar(100) | N |  |
| `categoryOID` |  | nchar(32) | Y |  |

#### `DefEntity` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `cmItemId` |  | nvarchar(100) | N |  |
| `cmItemName` |  | nvarchar(100) | N |  |
| `version` |  | int | N |  |
| `validFrom` |  | datetime | Y |  |
| `validTo` |  | datetime | Y |  |
| `etyStatus` |  | nvarchar(50) | N |  |
| `description` |  | nvarchar(1000) | Y |  |
| `createdTime` |  | datetime | N |  |
| `containerOID` |  | nchar(32) | N |  |
| `modelOID` |  | nchar(32) | Y |  |
| `dsOID` |  | nchar(32) | Y |  |
| `creatorOID` |  | nchar(32) | Y |  |

#### `DefaultSubstituteDefinition` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `ownerOID` |  | nchar(32) | Y |  |
| `substitutiveOrder` |  | int | N |  |
| `objectVersion` |  | int | N |  |
| `substituteOID` |  | nchar(32) | N |  |
| `startSubstituteTime` |  | datetime | Y |  |
| `endSubstituteTime` |  | datetime | Y |  |
| `defaultApply` |  | int | N |  |

### 前綴 `Des` — —（1 表）


#### `DesignTempFile` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `formDefinitionOID` |  | nchar(32) | N |  |
| `userOID` |  | nchar(32) | N |  |
| `formDefinitionId` |  | nvarchar(100) | N |  |
| `formDefinitionName` |  | nvarchar(100) | Y |  |
| `createdTime` |  | datetime | N |  |
| `categoryOID` |  | nchar(32) | Y |  |

### 前綴 `Vet` — —（1 表）


#### `VettingType` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | Y |  |
| `orgUnitOID` |  | nchar(32) | Y |  |
| `unitType` |  | nvarchar(50) | Y |  |
| `documentOID` |  | nchar(32) | Y |  |
| `vettingPeriod` |  | int | Y |  |
| `vettingNoticeDay` |  | int | Y |  |
| `vettingFrom` |  | datetime | Y |  |
| `vettingTo` |  | datetime | Y |  |
| `vettingPreNotice` |  | datetime | Y |  |
| `onlyUnitManager` |  | int | Y |  |

### 前綴 `Typ` — —（1 表）


#### `TypeDefinition` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `id` |  | nvarchar(100) | N |  |
| `typeDefinitionName` |  | nvarchar(100) | Y |  |
| `containerOID` |  | nchar(32) | Y |  |
| `contentOID` |  | nchar(32) | Y |  |
| `objectVersion` |  | int | N |  |
| `description` |  | ntext | Y |  |
| `toolOID` |  | nchar(32) | Y |  |

### 前綴 `ETL` — —（1 表）


#### `ETL_ForDelete` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `forDelete` |  | int | Y |  |

### 前綴 `Lay` — —（3 表）


#### `LayoutCmItem` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `cmItemId` |  | nvarchar(100) | N |  |
| `chkOutUserOID` |  | nchar(32) | Y |  |
| `chkOutTime` |  | datetime | Y |  |
| `chkInTime` |  | datetime | Y |  |
| `lastVersion` |  | int | N |  |
| `pubStatus` |  | nvarchar(50) | N |  |
| `cmItemName` |  | nvarchar(100) | N |  |
| `categoryOID` |  | nchar(32) | Y |  |

#### `LayoutEntity` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `cmItemId` |  | nvarchar(100) | N |  |
| `cmItemName` |  | nvarchar(100) | N |  |
| `version` |  | int | N |  |
| `validFrom` |  | datetime | Y |  |
| `validTo` |  | datetime | Y |  |
| `etyStatus` |  | nvarchar(50) | N |  |
| `description` |  | nvarchar(1000) | Y |  |
| `createdTime` |  | datetime | N |  |
| `creatorOID` |  | nchar(32) | Y |  |
| `serializedModel` |  | ntext | N |  |
| `containerOID` |  | nchar(32) | N |  |

#### `LayoutEntity_Platform` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `entityOID` |  | nchar(32) | N | PK |
| `platformOID` |  | nchar(32) | N | PK |

### 前綴 `QBi` — —（1 表）


#### `QBizModel` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `cmItemId` |  | nvarchar(100) | Y |  |
| `entityVersion` |  | int | N |  |
| `cusInsTableName` |  | nvarchar(100) | Y |  |
| `typeId` |  | nvarchar(100) | N |  |
| `serializedXSD` |  | ntext | N |  |
| `containerOID` |  | nchar(32) | Y |  |

### 前綴 `QEx` — —（1 表）


#### `QExtDataType` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `cmItemId` |  | nvarchar(100) | N |  |
| `typeId` |  | nvarchar(100) | N |  |
| `serializedXSD` |  | ntext | N |  |
| `containerOID` |  | nchar(32) | N |  |

### 前綴 `Tit` — —（2 表）


#### `Title` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `definitionOID` |  | nchar(32) | N |  |
| `organizationUnitOID` |  | nchar(32) | N |  |
| `occupantOID` |  | nchar(32) | N |  |

#### `TitleDefinition` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `titleDefinitionName` |  | nvarchar(100) | N |  |
| `shortName` |  | nvarchar(100) | Y |  |
| `organizationOID` |  | nchar(32) | Y |  |
| `description` |  | ntext | Y |  |

### 前綴 `QSe` — —（1 表）


#### `QServiceConfig` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `CfgKey` |  | nvarchar(255) | N | PK |
| `CfgValue` |  | nvarchar(255) | N |  |

### 前綴 `Dea` — —（1 表）


#### `Deadline` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `deadlineCondition` |  | nvarchar(100) | N |  |
| `containerOID` |  | nchar(32) | N |  |
| `exceptionName` |  | nvarchar(100) | N |  |
| `objectVersion` |  | int | N |  |
| `executionType` |  | nvarchar(50) | N |  |

### 前綴 `RDB` — —（1 表）


#### `RDBDataSource` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `dsId` |  | nvarchar(100) | N |  |
| `rdbDsType` |  | nvarchar(50) | N |  |

### 前綴 `EPM` — 企業流程管理(EPM)（34 表）


#### `EPM_BudgetCreateForm` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `processSerialNumber` |  | nvarchar(50) | Y |  |
| `formSerialNumber` |  | nvarchar(50) | Y |  |
| `companyId` |  | nvarchar(50) | Y |  |
| `companyName` |  | nvarchar(250) | Y |  |
| `companyDB` |  | nvarchar(50) | Y |  |
| `creator` |  | nvarchar(50) | Y |  |
| `creatorName` |  | nvarchar(250) | Y |  |
| `applicant` |  | nvarchar(50) | Y |  |
| `applicantName` |  | nvarchar(250) | Y |  |
| `applicantDeptId` |  | nvarchar(50) | Y |  |
| `applicantDeptName` |  | nvarchar(50) | Y |  |
| `applicationDate` |  | datetime | Y |  |
| `applicantERPDeptId` |  | nvarchar(50) | Y |  |
| `applicantERPDeptName` |  | nvarchar(250) | Y |  |
| `year` |  | nvarchar(4) | Y |  |
| `budgetNumber` |  | nvarchar(50) | Y |  |
| `budgetName` |  | nvarchar(250) | Y |  |
| `throwFailMessage` |  | nvarchar(max) | Y |  |

#### `EPM_BudgetCreateForm_grid` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(35) | N | PK |
| `formSerialNumber` |  | nvarchar(50) | Y |  |
| `serialNo` |  | nvarchar(4) | Y |  |
| `accountCode` |  | nvarchar(50) | Y |  |
| `accountName` |  | nvarchar(50) | Y |  |
| `yearBudgetAmount` |  | decimal(21,6) | Y |  |
| `budgetControl` |  | nvarchar(1) | Y |  |
| `budgetControlName` |  | nvarchar(50) | Y |  |
| `canNextPeriod` |  | nvarchar(1) | Y |  |
| `canNextPeriodName` |  | nvarchar(50) | Y |  |
| `totalControl` |  | nvarchar(1) | Y |  |
| `totalControlName` |  | nvarchar(50) | Y |  |
| `maintainUnit` |  | nvarchar(1) | Y |  |
| `maintainUnitName` |  | nvarchar(50) | Y |  |
| `period01` |  | nvarchar(7) | Y |  |
| `period02` |  | nvarchar(7) | Y |  |
| `period03` |  | nvarchar(7) | Y |  |
| `period04` |  | nvarchar(7) | Y |  |
| `period05` |  | nvarchar(7) | Y |  |
| `period06` |  | nvarchar(7) | Y |  |
| `period07` |  | nvarchar(7) | Y |  |
| `period08` |  | nvarchar(7) | Y |  |
| `period09` |  | nvarchar(7) | Y |  |
| `period10` |  | nvarchar(7) | Y |  |
| `period11` |  | nvarchar(7) | Y |  |
| `period12` |  | nvarchar(7) | Y |  |
| `period13` |  | nvarchar(7) | Y |  |

#### `EPM_BudgetDivertForm` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `processSerialNumber` |  | nvarchar(50) | Y |  |
| `formSerialNumber` |  | nvarchar(50) | Y |  |
| `companyId` |  | nvarchar(50) | Y |  |
| `companyName` |  | nvarchar(250) | Y |  |
| `companyDB` |  | nvarchar(50) | Y |  |
| `creator` |  | nvarchar(50) | Y |  |
| `creatorName` |  | nvarchar(250) | Y |  |
| `applicant` |  | nvarchar(50) | Y |  |
| `applicantName` |  | nvarchar(250) | Y |  |
| `applicantDeptId` |  | nvarchar(50) | Y |  |
| `applicantDeptName` |  | nvarchar(50) | Y |  |
| `divertDate` |  | datetime | Y |  |
| `applicantERPDeptId` |  | nvarchar(50) | Y |  |
| `applicantERPDeptName` |  | nvarchar(250) | Y |  |
| `divertAmount` |  | decimal(21,6) | Y |  |
| `changeRemark` |  | nvarchar(max) | Y |  |
| `throwFailMessage` |  | nvarchar(max) | Y |  |
| `sourceBudgetYear` |  | nvarchar(4) | Y |  |
| `sourceERPDeptId` |  | nvarchar(50) | Y |  |
| `sourceERPDeptName` |  | nvarchar(250) | Y |  |
| `sourceBudgetNumber` |  | nvarchar(50) | Y |  |
| `sourceBudgetName` |  | nvarchar(250) | Y |  |
| `sourceAccountCode` |  | nvarchar(50) | Y |  |
| `sourceAccountName` |  | nvarchar(50) | Y |  |
| `sourceBudgetPeriod` |  | nvarchar(10) | Y |  |
| `targetBudgetYear` |  | nvarchar(4) | Y |  |
| `targetERPDeptId` |  | nvarchar(50) | Y |  |
| `targetERPDeptName` |  | nvarchar(250) | Y |  |
| `targetBudgetNumber` |  | nvarchar(50) | Y |  |
| `targetBudgetName` |  | nvarchar(250) | Y |  |
| `targetAccountCode` |  | nvarchar(50) | Y |  |
| `targetAccountName` |  | nvarchar(50) | Y |  |
| `targetBudgetPeriod` |  | nvarchar(10) | Y |  |

#### `EPM_BudgetReviseForm` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `processSerialNumber` |  | nvarchar(50) | Y |  |
| `formSerialNumber` |  | nvarchar(50) | Y |  |
| `companyId` |  | nvarchar(50) | Y |  |
| `companyName` |  | nvarchar(250) | Y |  |
| `companyDB` |  | nvarchar(50) | Y |  |
| `creator` |  | nvarchar(50) | Y |  |
| `creatorName` |  | nvarchar(250) | Y |  |
| `applicant` |  | nvarchar(50) | Y |  |
| `applicantName` |  | nvarchar(250) | Y |  |
| `applicantDeptId` |  | nvarchar(50) | Y |  |
| `applicantDeptName` |  | nvarchar(50) | Y |  |
| `applicationDate` |  | datetime | Y |  |
| `applicantERPDeptId` |  | nvarchar(50) | Y |  |
| `applicantERPDeptName` |  | nvarchar(250) | Y |  |
| `changeDate` |  | datetime | Y |  |
| `changeRemark` |  | nvarchar(max) | Y |  |
| `year` |  | nvarchar(4) | Y |  |
| `total` |  | decimal(21,6) | Y |  |
| `budgetNumber` |  | nvarchar(50) | Y |  |
| `budgetName` |  | nvarchar(250) | Y |  |
| `throwFailMessage` |  | nvarchar(max) | Y |  |

#### `EPM_BudgetReviseForm_grid` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(35) | N | PK |
| `formSerialNumber` |  | nvarchar(50) | Y |  |
| `budgetRevise` |  | nvarchar(1) | Y |  |
| `budgetReviseName` |  | nvarchar(50) | Y |  |
| `accountCode` |  | nvarchar(50) | Y |  |
| `accountName` |  | nvarchar(50) | Y |  |
| `budgetPeriod` |  | nvarchar(10) | Y |  |
| `reviseAmount` |  | decimal(21,6) | Y |  |

#### `EPM_Category` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `categoryCode` |  | nvarchar(50) | Y |  |
| `categoryName` |  | nvarchar(50) | Y |  |
| `disabled` |  | nvarchar(1) | Y |  |
| `remark` |  | nvarchar(max) | Y |  |
| `maxAmount` |  | decimal(21,6) | Y |  |
| `overAction` |  | nvarchar(1) | Y |  |
| `controlLocal` |  | nvarchar(1) | Y |  |
| `controlLevel` |  | nvarchar(1) | Y |  |
| `bpmCompanyId` |  | nvarchar(50) | Y |  |
| `scope` |  | nvarchar(1) | Y |  |

#### `EPM_CategoryLevel` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `categoryCode` |  | nvarchar(50) | Y |  |
| `levelCode` |  | nvarchar(50) | Y |  |
| `maxAmount` |  | decimal(21,6) | Y |  |

#### `EPM_CategoryLocal` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `categoryCode` |  | nvarchar(50) | Y |  |
| `localCode` |  | nvarchar(50) | Y |  |
| `maxAmount` |  | decimal(21,6) | Y |  |

#### `EPM_Company` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `companyId` |  | nvarchar(50) | Y |  |
| `companyName` |  | nvarchar(250) | Y |  |
| `companyDB` |  | nvarchar(50) | Y |  |
| `disabled` |  | nvarchar(1) | Y |  |
| `currencyCode` |  | nvarchar(10) | Y |  |
| `currencyName` |  | nvarchar(20) | Y |  |
| `bgDisabled` |  | nvarchar(1) | Y |  |
| `taxAccount` |  | nvarchar(50) | Y |  |
| `taxAccountName` |  | nvarchar(250) | Y |  |
| `supportMed` |  | nvarchar(1) | Y |  |
| `allowanceCode` |  | nvarchar(50) | Y |  |
| `allowanceCodeName` |  | nvarchar(250) | Y |  |

#### `EPM_CompanyBudget` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `companyId` |  | nvarchar(50) | Y |  |
| `budgetNumber` |  | nvarchar(50) | Y |  |
| `budgetName` |  | nvarchar(250) | Y |  |
| `year` |  | nvarchar(4) | Y |  |
| `disabled` |  | nvarchar(1) | Y |  |

#### `EPM_Config` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `pKey` |  | nvarchar(10) | Y |  |
| `ERPVersion` |  | nvarchar(50) | Y |  |
| `ERPWSURL` |  | nvarchar(250) | Y |  |
| `EmplExpenseProgId` |  | nvarchar(50) | Y |  |
| `EmplLoanProgId` |  | nvarchar(50) | Y |  |
| `VoucherDeclaration` |  | nvarchar(1) | Y |  |
| `InputMixedTax` |  | nvarchar(1) | Y |  |
| `IsSingleLimit` |  | nvarchar(1) | Y |  |

#### `EPM_CostCenter` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `companyId` |  | nvarchar(50) | Y |  |
| `costCenterCode` |  | nvarchar(50) | Y |  |
| `costCenterName` |  | nvarchar(50) | Y |  |
| `formIdForEmpl` |  | nvarchar(50) | Y |  |
| `formNameForEmpl` |  | nvarchar(50) | Y |  |
| `AAPCategoryCode` |  | nvarchar(50) | Y |  |
| `AAPCategoryName` |  | nvarchar(50) | Y |  |
| `formIdForVendor` |  | nvarchar(50) | Y |  |
| `formNameForVendor` |  | nvarchar(50) | Y |  |
| `AAP15CategoryCode` |  | nvarchar(50) | Y |  |
| `AAP15CategoryName` |  | nvarchar(50) | Y |  |
| `prepaidFormIDForEmpl` |  | nvarchar(50) | Y |  |
| `prepaidFormNameForEmpl` |  | nvarchar(50) | Y |  |
| `prepaidFormIDForVendor` |  | nvarchar(50) | Y |  |
| `prepaidFormNameForVendor` |  | nvarchar(50) | Y |  |
| `paymentCode` |  | nvarchar(50) | Y |  |
| `paymentName` |  | nvarchar(250) | Y |  |

#### `EPM_CostCenterCategory` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `companyId` |  | nvarchar(50) | Y |  |
| `costCenterCode` |  | nvarchar(50) | Y |  |
| `categoryCode` |  | nvarchar(50) | Y |  |
| `erpCategoryCode` |  | nvarchar(50) | Y |  |
| `erpCategoryName` |  | nvarchar(50) | Y |  |
| `accountCode` |  | nvarchar(50) | Y |  |
| `accountName` |  | nvarchar(50) | Y |  |
| `reasonCode` |  | nvarchar(50) | Y |  |
| `reasonName` |  | nvarchar(50) | Y |  |
| `taxCode` |  | nvarchar(50) | Y |  |
| `taxName` |  | nvarchar(50) | Y |  |
| `tax` |  | decimal(5,2) | Y |  |
| `declarationFormat` |  | nvarchar(50) | Y |  |
| `deduction` |  | nvarchar(1) | Y |  |
| `taxation` |  | nvarchar(1) | Y |  |
| `taxIdNumber` |  | nvarchar(50) | Y |  |
| `invoiceType` |  | nvarchar(1) | Y |  |
| `taxIncluded` |  | nvarchar(1) | Y |  |
| `sellersTaxIdNumber` |  | nvarchar(50) | Y |  |
| `invoiceCode` |  | nvarchar(50) | Y |  |
| `invoiceName` |  | nvarchar(50) | Y |  |
| `documentType` |  | nvarchar(1) | Y |  |
| `documentTypeName` |  | nvarchar(50) | Y |  |

#### `EPM_CostCenterDept` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `companyId` |  | nvarchar(50) | Y |  |
| `costCenterCode` |  | nvarchar(50) | Y |  |
| `deptId` |  | nvarchar(50) | Y |  |
| `deptName` |  | nvarchar(50) | Y |  |

#### `EPM_Currency` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `companyId` |  | nvarchar(50) | Y |  |
| `currencyCode` |  | nvarchar(50) | Y |  |
| `currencyName` |  | nvarchar(50) | Y |  |
| `priceDigit` |  | int | Y |  |
| `amountDigit` |  | int | Y |  |
| `totalDigit` |  | int | Y |  |

#### `EPM_ExchangeRate` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `companyId` |  | nvarchar(50) | Y |  |
| `currencyCode` |  | nvarchar(50) | Y |  |
| `effectiveDate` |  | datetime | Y |  |
| `exchangeRate` |  | decimal(20,9) | Y |  |

#### `EPM_ExpenseForm` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nvarchar(32) | N | PK |
| `processSerialNumber` |  | nvarchar(50) | Y |  |
| `formSerialNumber` |  | nvarchar(50) | Y |  |
| `companyId` |  | nvarchar(50) | Y |  |
| `companyName` |  | nvarchar(250) | Y |  |
| `companyDB` |  | nvarchar(50) | Y |  |
| `creator` |  | nvarchar(50) | Y |  |
| `creatorName` |  | nvarchar(250) | Y |  |
| `applicant` |  | nvarchar(50) | Y |  |
| `applicantName` |  | nvarchar(250) | Y |  |
| `applicantDeptId` |  | nvarchar(50) | Y |  |
| `applicantDeptName` |  | nvarchar(250) | Y |  |
| `applicationDate` |  | datetime | Y |  |
| `accountDate` |  | datetime | Y |  |
| `applicantERPDeptId` |  | nvarchar(50) | Y |  |
| `applicantERPDeptName` |  | nvarchar(250) | Y |  |
| `ERPFormId` |  | nvarchar(50) | Y |  |
| `ERPFormName` |  | nvarchar(250) | Y |  |
| `costCenterCode` |  | nvarchar(50) | Y |  |
| `costCenterName` |  | nvarchar(250) | Y |  |
| `localCurrencyCode` |  | nvarchar(50) | Y |  |
| `localCurrencyName` |  | nvarchar(50) | Y |  |
| `localTotal` |  | decimal(21,6) | Y |  |
| `headRemark` |  | nvarchar(250) | Y |  |
| `ERPFormSerailNumber` |  | nvarchar(50) | Y |  |
| `throwFailMessage` |  | nvarchar(max) | Y |  |
| `exchangeRate` |  | decimal(20,9) | Y |  |
| `awaitingLocalTotal` |  | decimal(21,6) | Y |  |
| `awaitingNumber` |  | nvarchar(max) | Y |  |
| `localTotalAmountUnTaxed` |  | decimal(21,6) | Y |  |
| `localTotalTax` |  | decimal(21,6) | Y |  |
| `localTotalAmountWithTax` |  | decimal(21,6) | Y |  |
| `projectCode1` |  | nvarchar(50) | Y |  |
| `projectName1` |  | nvarchar(250) | Y |  |
| `budgetNumber` |  | nvarchar(50) | Y |  |

#### `EPM_ExpenseForm_CM` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nvarchar(32) | N | PK |
| `processSerialNumber` |  | nvarchar(50) | Y |  |
| `formSerialNumber` |  | nvarchar(50) | Y |  |
| `companyId` |  | nvarchar(50) | Y |  |
| `companyName` |  | nvarchar(250) | Y |  |
| `companyDB` |  | nvarchar(50) | Y |  |
| `creator` |  | nvarchar(50) | Y |  |
| `creatorName` |  | nvarchar(250) | Y |  |
| `applicant` |  | nvarchar(50) | Y |  |
| `applicantName` |  | nvarchar(250) | Y |  |
| `applicantDeptId` |  | nvarchar(50) | Y |  |
| `applicantDeptName` |  | nvarchar(250) | Y |  |
| `applicationDate` |  | datetime | Y |  |
| `accountDate` |  | datetime | Y |  |
| `applicantERPDeptId` |  | nvarchar(50) | Y |  |
| `applicantERPDeptName` |  | nvarchar(250) | Y |  |
| `ERPFormId` |  | nvarchar(50) | Y |  |
| `ERPFormName` |  | nvarchar(250) | Y |  |
| `costCenterCode` |  | nvarchar(50) | Y |  |
| `costCenterName` |  | nvarchar(250) | Y |  |
| `localCurrencyCode` |  | nvarchar(50) | Y |  |
| `localCurrencyName` |  | nvarchar(50) | Y |  |
| `localTotal` |  | decimal(21,6) | Y |  |
| `headRemark` |  | nvarchar(250) | Y |  |
| `ERPFormSerailNumber` |  | nvarchar(50) | Y |  |
| `throwFailMessage` |  | nvarchar(max) | Y |  |
| `localTotalAmountUnTaxed` |  | decimal(21,6) | Y |  |
| `localTotalTax` |  | decimal(21,6) | Y |  |
| `localTotalAmountWithTax` |  | decimal(21,6) | Y |  |
| `supportMed` |  | nvarchar(50) | Y |  |
| `supportMedName` |  | nvarchar(250) | Y |  |
| `allowanceCode` |  | nvarchar(50) | Y |  |
| `allowanceName` |  | nvarchar(250) | Y |  |
| `objectCode` |  | nvarchar(50) | Y |  |
| `objectName` |  | nvarchar(250) | Y |  |
| `paymentCode` |  | nvarchar(50) | Y |  |
| `paymentName` |  | nvarchar(250) | Y |  |

#### `EPM_ExpenseForm_CM_grid` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nvarchar(35) | N | PK |
| `formSerialNumber` |  | nvarchar(50) | Y |  |
| `serialNo` |  | nvarchar(4) | Y |  |
| `expenseDept_txt` |  | nvarchar(50) | Y |  |
| `expenseDept_lbl` |  | nvarchar(250) | Y |  |
| `categoryCode_txt` |  | nvarchar(50) | Y |  |
| `categoryCode_lbl` |  | nvarchar(50) | Y |  |
| `ERPCategoryCode_txt` |  | nvarchar(50) | Y |  |
| `ERPCategoryCode_lbl` |  | nvarchar(50) | Y |  |
| `accountCodeWindow_txt` |  | nvarchar(50) | Y |  |
| `accountCodeWindow_lbl` |  | nvarchar(50) | Y |  |
| `certificateDate_txt` |  | datetime | Y |  |
| `currencyCode_txt` |  | nvarchar(50) | Y |  |
| `currencyCode_lbl` |  | nvarchar(50) | Y |  |
| `amount` |  | decimal(21,6) | Y |  |
| `exchangeRate` |  | decimal(20,9) | Y |  |
| `qty` |  | decimal(15,3) | Y |  |
| `localAmount` |  | decimal(21,6) | Y |  |
| `remark` |  | nvarchar(max) | Y |  |
| `sellersTaxIdNumber` |  | nvarchar(50) | Y |  |
| `invoiceNumber` |  | nvarchar(500) | Y |  |
| `localCode_txt` |  | nvarchar(50) | Y |  |
| `localCode_lbl` |  | nvarchar(50) | Y |  |
| `taxCode` |  | nvarchar(50) | Y |  |
| `taxCodeName` |  | nvarchar(150) | Y |  |
| `amountUnTaxed` |  | decimal(21,6) | Y |  |
| `tax` |  | decimal(21,6) | Y |  |
| `amountWithTax` |  | decimal(21,6) | Y |  |
| `localAmountUnTaxed` |  | decimal(21,6) | Y |  |
| `localTax` |  | decimal(21,6) | Y |  |
| `localAmountWithTax` |  | decimal(21,6) | Y |  |
| `projectCode2_txt` |  | nvarchar(50) | Y |  |
| `projectCode2_lbl` |  | nvarchar(250) | Y |  |
| `documentType` |  | nvarchar(1) | Y |  |
| `documentTypeName` |  | nvarchar(50) | Y |  |
| `invoiceType` |  | nvarchar(50) | Y |  |
| `invoiceTypeName` |  | nvarchar(150) | Y |  |
| `deduction` |  | nvarchar(50) | Y |  |
| `deductionName` |  | nvarchar(150) | Y |  |
| `taxPercentage` |  | nvarchar(50) | Y |  |
| `txtTax` |  | decimal(21,6) | Y |  |
| `invoiceAmountUnTaxed` |  | decimal(21,6) | Y |  |
| `invoiceTax` |  | decimal(21,6) | Y |  |
| `invoiceLocalAmountUnTaxed` |  | decimal(21,6) | Y |  |
| `invoiceLocalTax` |  | decimal(21,6) | Y |  |

#### `EPM_ExpenseForm_grid` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nvarchar(35) | N | PK |
| `formSerialNumber` |  | nvarchar(50) | Y |  |
| `serialNo` |  | nvarchar(4) | Y |  |
| `categoryCode_txt` |  | nvarchar(50) | Y |  |
| `categoryCode_lbl` |  | nvarchar(50) | Y |  |
| `certificateDate_txt` |  | datetime | Y |  |
| `currencyCode_txt` |  | nvarchar(50) | Y |  |
| `currencyCode_lbl` |  | nvarchar(50) | Y |  |
| `amount` |  | decimal(21,6) | Y |  |
| `invoiceAmount` |  | decimal(21,6) | Y |  |
| `exchangeRate` |  | decimal(20,9) | Y |  |
| `localAmount` |  | decimal(21,6) | Y |  |
| `remark` |  | nvarchar(max) | Y |  |
| `sellersTaxIdNumber` |  | nvarchar(50) | Y |  |
| `invoiceNumber` |  | nvarchar(500) | Y |  |
| `localCode_txt` |  | nvarchar(50) | Y |  |
| `localCode_lbl` |  | nvarchar(50) | Y |  |
| `taxCode` |  | nvarchar(50) | Y |  |
| `taxName` |  | nvarchar(50) | Y |  |
| `amountUnTaxed` |  | decimal(21,6) | Y |  |
| `tax` |  | decimal(21,6) | Y |  |
| `amountWithTax` |  | decimal(21,6) | Y |  |
| `localAmountUnTaxed` |  | decimal(21,6) | Y |  |
| `localTax` |  | decimal(21,6) | Y |  |
| `localAmountWithTax` |  | decimal(21,6) | Y |  |
| `projectCode2_txt` |  | nvarchar(50) | Y |  |
| `projectCode2_lbl` |  | nvarchar(250) | Y |  |
| `WBSCode_txt` |  | nvarchar(50) | Y |  |
| `WBSCode_lbl` |  | nvarchar(250) | Y |  |
| `documentType` |  | nvarchar(1) | Y |  |
| `documentTypeName` |  | nvarchar(50) | Y |  |
| `pcmi05formno` |  | nvarchar(50) | Y |  |
| `budgetPeriod` |  | nvarchar(10) | Y |  |
| `accountItem01` |  | nvarchar(250) | Y |  |
| `accountItem02` |  | nvarchar(250) | Y |  |
| `accountItem03` |  | nvarchar(250) | Y |  |
| `accountItem04` |  | nvarchar(250) | Y |  |
| `accountItem05` |  | nvarchar(250) | Y |  |
| `accountItem06` |  | nvarchar(250) | Y |  |
| `accountItem07` |  | nvarchar(250) | Y |  |
| `accountItem08` |  | nvarchar(250) | Y |  |
| `accountItem09` |  | nvarchar(250) | Y |  |
| `accountItem10` |  | nvarchar(250) | Y |  |

#### `EPM_ExpenseForm_grid2` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nvarchar(255) | N | PK |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `gInvoiceItem` |  | nvarchar(255) | Y |  |
| `gItem` |  | nvarchar(255) | Y |  |
| `gApplicantERPDeptId` |  | nvarchar(255) | Y |  |
| `gApplicantERPDeptName` |  | nvarchar(255) | Y |  |
| `gAmount` |  | nvarchar(255) | Y |  |
| `gAmountUnTaxed` |  | nvarchar(255) | Y |  |
| `gTax` |  | nvarchar(255) | Y |  |
| `gLocalAmount` |  | nvarchar(255) | Y |  |
| `gLocalAmountUnTaxed` |  | nvarchar(255) | Y |  |
| `gLocalTax` |  | nvarchar(255) | Y |  |
| `gAccountCode` |  | nvarchar(255) | Y |  |
| `reasonCode` |  | nvarchar(50) | Y |  |
| `reasonName` |  | nvarchar(50) | Y |  |

#### `EPM_ExpenseForm_grid3` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nvarchar(255) | N | PK |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `gT100AwaitingNumber` |  | nvarchar(255) | Y |  |
| `gT100ANItem` |  | nvarchar(255) | Y |  |
| `gT100ANOriAmount` |  | nvarchar(255) | Y |  |
| `gT100ANLocAmount` |  | nvarchar(255) | Y |  |
| `gT100apcOriAmount` |  | nvarchar(255) | Y |  |
| `gT100apcLocAmount` |  | nvarchar(255) | Y |  |

#### `EPM_Local` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `localCode` |  | nvarchar(50) | Y |  |
| `localName` |  | nvarchar(50) | Y |  |

#### `EPM_PrepaidExpenseForm` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nvarchar(32) | N | PK |
| `processSerialNumber` |  | nvarchar(50) | Y |  |
| `formSerialNumber` |  | nvarchar(50) | Y |  |
| `companyId` |  | nvarchar(50) | Y |  |
| `companyName` |  | nvarchar(250) | Y |  |
| `companyDB` |  | nvarchar(50) | Y |  |
| `creator` |  | nvarchar(50) | Y |  |
| `creatorName` |  | nvarchar(250) | Y |  |
| `applicant` |  | nvarchar(50) | Y |  |
| `applicantName` |  | nvarchar(250) | Y |  |
| `applicantDeptId` |  | nvarchar(50) | Y |  |
| `applicantDeptName` |  | nvarchar(250) | Y |  |
| `applicationDate` |  | datetime | Y |  |
| `accountDate` |  | datetime | Y |  |
| `applicantERPDeptId` |  | nvarchar(50) | Y |  |
| `applicantERPDeptName` |  | nvarchar(250) | Y |  |
| `ERPFormId` |  | nvarchar(50) | Y |  |
| `ERPFormName` |  | nvarchar(250) | Y |  |
| `costCenterCode` |  | nvarchar(50) | Y |  |
| `costCenterName` |  | nvarchar(250) | Y |  |
| `localCurrencyCode` |  | nvarchar(50) | Y |  |
| `localCurrencyName` |  | nvarchar(50) | Y |  |
| `localTotal` |  | decimal(21,6) | Y |  |
| `ERPFormSerailNumber` |  | nvarchar(50) | Y |  |
| `throwFailMessage` |  | nvarchar(max) | Y |  |
| `exchangeRate` |  | decimal(20,9) | Y |  |
| `remark2` |  | nvarchar(max) | Y |  |
| `taxCode` |  | nvarchar(50) | Y |  |
| `taxName` |  | nvarchar(250) | Y |  |
| `localTotalAmountUnTaxed` |  | decimal(21,6) | Y |  |
| `localTotalTax` |  | decimal(21,6) | Y |  |
| `localTotalAmountWithTax` |  | decimal(21,6) | Y |  |
| `projectCode1` |  | nvarchar(50) | Y |  |
| `projectName1` |  | nvarchar(250) | Y |  |
| `currencyCode` |  | nvarchar(50) | Y |  |
| `currencyName` |  | nvarchar(50) | Y |  |
| `total` |  | decimal(21,6) | Y |  |

#### `EPM_PrepaidExpenseForm_grid` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nvarchar(35) | N | PK |
| `formSerialNumber` |  | nvarchar(50) | Y |  |
| `serialNo` |  | nvarchar(4) | Y |  |
| `categoryCode_txt` |  | nvarchar(50) | Y |  |
| `categoryCode_lbl` |  | nvarchar(50) | Y |  |
| `amount` |  | decimal(21,6) | Y |  |
| `remark` |  | nvarchar(max) | Y |  |
| `taxCode2` |  | nvarchar(50) | Y |  |
| `taxName2` |  | nvarchar(50) | Y |  |
| `amountUnTaxed` |  | decimal(21,6) | Y |  |
| `tax` |  | decimal(21,6) | Y |  |
| `amountWithTax` |  | decimal(21,6) | Y |  |
| `localAmountUnTaxed` |  | decimal(21,6) | Y |  |
| `localTax` |  | decimal(21,6) | Y |  |
| `localAmountWithTax` |  | decimal(21,6) | Y |  |
| `projectCode2_txt` |  | nvarchar(50) | Y |  |
| `projectCode2_lbl` |  | nvarchar(250) | Y |  |
| `WBSCode_txt` |  | nvarchar(50) | Y |  |
| `WBSCode_lbl` |  | nvarchar(250) | Y |  |

#### `EPM_PrepaidVendorForm` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nvarchar(32) | N | PK |
| `processSerialNumber` |  | nvarchar(50) | Y |  |
| `formSerialNumber` |  | nvarchar(50) | Y |  |
| `companyId` |  | nvarchar(50) | Y |  |
| `companyName` |  | nvarchar(250) | Y |  |
| `companyDB` |  | nvarchar(50) | Y |  |
| `creator` |  | nvarchar(50) | Y |  |
| `creatorName` |  | nvarchar(250) | Y |  |
| `applicant` |  | nvarchar(50) | Y |  |
| `applicantName` |  | nvarchar(250) | Y |  |
| `applicantDeptId` |  | nvarchar(50) | Y |  |
| `applicantDeptName` |  | nvarchar(250) | Y |  |
| `applicationDate` |  | datetime | Y |  |
| `accountDate` |  | datetime | Y |  |
| `applicantERPDeptId` |  | nvarchar(50) | Y |  |
| `applicantERPDeptName` |  | nvarchar(250) | Y |  |
| `ERPFormId` |  | nvarchar(50) | Y |  |
| `ERPFormName` |  | nvarchar(250) | Y |  |
| `costCenterCode` |  | nvarchar(50) | Y |  |
| `costCenterName` |  | nvarchar(250) | Y |  |
| `localCurrencyCode` |  | nvarchar(50) | Y |  |
| `localCurrencyName` |  | nvarchar(50) | Y |  |
| `localTotal` |  | decimal(21,6) | Y |  |
| `ERPFormSerailNumber` |  | nvarchar(50) | Y |  |
| `throwFailMessage` |  | nvarchar(max) | Y |  |
| `exchangeRate` |  | decimal(20,9) | Y |  |
| `vendorCode` |  | nvarchar(50) | Y |  |
| `vendorName` |  | nvarchar(250) | Y |  |
| `paymentCode` |  | nvarchar(50) | Y |  |
| `paymentName` |  | nvarchar(250) | Y |  |
| `taxCode` |  | nvarchar(50) | Y |  |
| `taxName` |  | nvarchar(250) | Y |  |
| `remark2` |  | nvarchar(max) | Y |  |
| `totalAmountUnTaxed` |  | decimal(21,6) | Y |  |
| `totalTax` |  | decimal(21,6) | Y |  |
| `totalAmountWithTax` |  | decimal(21,6) | Y |  |
| `localTotalAmountUnTaxed` |  | decimal(21,6) | Y |  |
| `localTotalTax` |  | decimal(21,6) | Y |  |
| `localTotalAmountWithTax` |  | decimal(21,6) | Y |  |
| `projectCode1` |  | nvarchar(50) | Y |  |
| `projectName1` |  | nvarchar(250) | Y |  |
| `payMoneyVendorCode` |  | nvarchar(50) | Y |  |
| `payMoneyVendorName` |  | nvarchar(250) | Y |  |
| `currencyCode` |  | nvarchar(50) | Y |  |
| `currencyName` |  | nvarchar(50) | Y |  |
| `total` |  | decimal(21,6) | Y |  |
| `sellersTaxIdNumber2` |  | nvarchar(50) | Y |  |
| `invoiceNumber2` |  | nvarchar(500) | Y |  |
| `certificateDate2` |  | datetime | Y |  |
| `deduction` |  | nvarchar(1) | Y |  |
| `deductionName` |  | nvarchar(50) | Y |  |

#### `EPM_PrepaidVendorForm_CM` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nvarchar(32) | N | PK |
| `processSerialNumber` |  | nvarchar(50) | Y |  |
| `formSerialNumber` |  | nvarchar(50) | Y |  |
| `companyId` |  | nvarchar(50) | Y |  |
| `companyName` |  | nvarchar(250) | Y |  |
| `companyDB` |  | nvarchar(50) | Y |  |
| `creator` |  | nvarchar(50) | Y |  |
| `creatorName` |  | nvarchar(250) | Y |  |
| `applicant` |  | nvarchar(50) | Y |  |
| `applicantName` |  | nvarchar(250) | Y |  |
| `applicantDeptId` |  | nvarchar(50) | Y |  |
| `applicantDeptName` |  | nvarchar(250) | Y |  |
| `applicationDate` |  | datetime | Y |  |
| `accountDate` |  | datetime | Y |  |
| `applicantERPDeptId` |  | nvarchar(50) | Y |  |
| `applicantERPDeptName` |  | nvarchar(250) | Y |  |
| `ERPFormId` |  | nvarchar(50) | Y |  |
| `ERPFormName` |  | nvarchar(250) | Y |  |
| `costCenterCode` |  | nvarchar(50) | Y |  |
| `costCenterName` |  | nvarchar(250) | Y |  |
| `localCurrencyCode` |  | nvarchar(50) | Y |  |
| `localCurrencyName` |  | nvarchar(50) | Y |  |
| `localTotal` |  | decimal(21,6) | Y |  |
| `ERPFormSerailNumber` |  | nvarchar(50) | Y |  |
| `throwFailMessage` |  | nvarchar(max) | Y |  |
| `exchangeRate` |  | decimal(20,9) | Y |  |
| `vendorCode` |  | nvarchar(50) | Y |  |
| `vendorName` |  | nvarchar(250) | Y |  |
| `paymentCode` |  | nvarchar(50) | Y |  |
| `paymentName` |  | nvarchar(250) | Y |  |
| `invoiceType` |  | nvarchar(50) | Y |  |
| `invoiceTypeName` |  | nvarchar(250) | Y |  |
| `taxCode` |  | nvarchar(50) | Y |  |
| `taxName` |  | nvarchar(250) | Y |  |
| `taxPercentage` |  | nvarchar(250) | Y |  |
| `txtTax` |  | decimal(21,6) | Y |  |
| `remark2` |  | nvarchar(max) | Y |  |
| `totalAmountUnTaxed` |  | decimal(21,6) | Y |  |
| `totalTax` |  | decimal(21,6) | Y |  |
| `totalAmountWithTax` |  | decimal(21,6) | Y |  |
| `localTotalAmountUnTaxed` |  | decimal(21,6) | Y |  |
| `localTotalTax` |  | decimal(21,6) | Y |  |
| `localTotalAmountWithTax` |  | decimal(21,6) | Y |  |
| `currencyCode` |  | nvarchar(50) | Y |  |
| `currencyName` |  | nvarchar(50) | Y |  |
| `total` |  | decimal(21,6) | Y |  |
| `sellersTaxIdNumber2` |  | nvarchar(50) | Y |  |
| `invoiceNumber2` |  | nvarchar(500) | Y |  |
| `certificateDate2` |  | datetime | Y |  |
| `deduction` |  | nvarchar(1) | Y |  |
| `deductionName` |  | nvarchar(50) | Y |  |

#### `EPM_PrepaidVendorForm_CM_grid` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nvarchar(35) | N | PK |
| `formSerialNumber` |  | nvarchar(50) | Y |  |
| `serialNo` |  | nvarchar(4) | Y |  |
| `expenseDept_txt` |  | nvarchar(50) | Y |  |
| `expenseDept_lbl` |  | nvarchar(250) | Y |  |
| `categoryCode_txt` |  | nvarchar(50) | Y |  |
| `categoryCode_lbl` |  | nvarchar(50) | Y |  |
| `ERPCategoryCode_txt` |  | nvarchar(50) | Y |  |
| `ERPCategoryCode_lbl` |  | nvarchar(50) | Y |  |
| `accountCodeWindow_txt` |  | nvarchar(50) | Y |  |
| `accountCodeWindow_lbl` |  | nvarchar(50) | Y |  |
| `amount` |  | decimal(21,6) | Y |  |
| `PURNumber_txt` |  | nvarchar(50) | Y |  |
| `remark` |  | nvarchar(max) | Y |  |
| `amountUnTaxed` |  | decimal(21,6) | Y |  |
| `tax` |  | decimal(21,6) | Y |  |
| `amountWithTax` |  | decimal(21,6) | Y |  |
| `localAmountUnTaxed` |  | decimal(21,6) | Y |  |
| `localTax` |  | decimal(21,6) | Y |  |
| `localAmountWithTax` |  | decimal(21,6) | Y |  |
| `projectCode2_txt` |  | nvarchar(50) | Y |  |
| `projectCode2_lbl` |  | nvarchar(250) | Y |  |

#### `EPM_PrepaidVendorForm_grid` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nvarchar(35) | N | PK |
| `formSerialNumber` |  | nvarchar(50) | Y |  |
| `serialNo` |  | nvarchar(4) | Y |  |
| `categoryCode_txt` |  | nvarchar(50) | Y |  |
| `categoryCode_lbl` |  | nvarchar(50) | Y |  |
| `certificateDate_txt` |  | datetime | Y |  |
| `amount` |  | decimal(21,6) | Y |  |
| `PURNumber_txt` |  | nvarchar(50) | Y |  |
| `invoiceNumber` |  | nvarchar(500) | Y |  |
| `sellersTaxIdNumber` |  | nvarchar(50) | Y |  |
| `itemCode_txt` |  | nvarchar(80) | Y |  |
| `itemName` |  | nvarchar(120) | Y |  |
| `qty` |  | decimal(15,3) | Y |  |
| `PURUnit` |  | nvarchar(50) | Y |  |
| `PURExchangeRate` |  | nvarchar(50) | Y |  |
| `taxCode2` |  | nvarchar(50) | Y |  |
| `taxName2` |  | nvarchar(50) | Y |  |
| `remark` |  | nvarchar(max) | Y |  |
| `amountUnTaxed` |  | decimal(21,6) | Y |  |
| `tax` |  | decimal(21,6) | Y |  |
| `amountWithTax` |  | decimal(21,6) | Y |  |
| `localAmountUnTaxed` |  | decimal(21,6) | Y |  |
| `localTax` |  | decimal(21,6) | Y |  |
| `localAmountWithTax` |  | decimal(21,6) | Y |  |
| `projectCode2_txt` |  | nvarchar(50) | Y |  |
| `projectCode2_lbl` |  | nvarchar(250) | Y |  |
| `WBSCode_txt` |  | nvarchar(50) | Y |  |
| `WBSCode_lbl` |  | nvarchar(250) | Y |  |
| `period_txt` |  | nvarchar(4) | Y |  |

#### `EPM_VendorRequestForm` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nvarchar(32) | N | PK |
| `processSerialNumber` |  | nvarchar(50) | Y |  |
| `formSerialNumber` |  | nvarchar(50) | Y |  |
| `companyId` |  | nvarchar(50) | Y |  |
| `companyName` |  | nvarchar(250) | Y |  |
| `companyDB` |  | nvarchar(50) | Y |  |
| `creator` |  | nvarchar(50) | Y |  |
| `creatorName` |  | nvarchar(250) | Y |  |
| `applicant` |  | nvarchar(50) | Y |  |
| `applicantName` |  | nvarchar(250) | Y |  |
| `applicantDeptId` |  | nvarchar(50) | Y |  |
| `applicantDeptName` |  | nvarchar(250) | Y |  |
| `applicationDate` |  | datetime | Y |  |
| `accountDate` |  | datetime | Y |  |
| `applicantERPDeptId` |  | nvarchar(50) | Y |  |
| `applicantERPDeptName` |  | nvarchar(250) | Y |  |
| `ERPFormId` |  | nvarchar(50) | Y |  |
| `ERPFormName` |  | nvarchar(250) | Y |  |
| `costCenterCode` |  | nvarchar(50) | Y |  |
| `costCenterName` |  | nvarchar(250) | Y |  |
| `localCurrencyCode` |  | nvarchar(50) | Y |  |
| `localCurrencyName` |  | nvarchar(50) | Y |  |
| `localTotal` |  | decimal(21,6) | Y |  |
| `ERPFormSerailNumber` |  | nvarchar(50) | Y |  |
| `throwFailMessage` |  | nvarchar(max) | Y |  |
| `exchangeRate` |  | decimal(20,9) | Y |  |
| `vendorCode` |  | nvarchar(50) | Y |  |
| `vendorName` |  | nvarchar(250) | Y |  |
| `paymentCode` |  | nvarchar(50) | Y |  |
| `paymentName` |  | nvarchar(250) | Y |  |
| `taxCode` |  | nvarchar(50) | Y |  |
| `taxName` |  | nvarchar(250) | Y |  |
| `remark` |  | nvarchar(max) | Y |  |
| `awaitingTotal` |  | decimal(21,6) | Y |  |
| `awaitingLocalTotal` |  | decimal(21,6) | Y |  |
| `awaitingNumber` |  | nvarchar(max) | Y |  |
| `totalAmountUnTaxed` |  | decimal(21,6) | Y |  |
| `totalTax` |  | decimal(21,6) | Y |  |
| `totalAmountWithTax` |  | decimal(21,6) | Y |  |
| `localTotalAmountUnTaxed` |  | decimal(21,6) | Y |  |
| `localTotalTax` |  | decimal(21,6) | Y |  |
| `localTotalAmountWithTax` |  | decimal(21,6) | Y |  |
| `projectCode1` |  | nvarchar(50) | Y |  |
| `projectName1` |  | nvarchar(250) | Y |  |
| `currencyCode` |  | nvarchar(50) | Y |  |
| `currencyName` |  | nvarchar(50) | Y |  |
| `total` |  | decimal(21,6) | Y |  |
| `sellersTaxIdNumber2` |  | nvarchar(50) | Y |  |
| `invoiceNumber2` |  | nvarchar(500) | Y |  |
| `certificateDate2` |  | datetime | Y |  |
| `deduction` |  | nvarchar(1) | Y |  |
| `deductionName` |  | nvarchar(50) | Y |  |
| `budgetNumber` |  | nvarchar(50) | Y |  |

#### `EPM_VendorRequestForm_CM` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nvarchar(32) | N | PK |
| `processSerialNumber` |  | nvarchar(50) | Y |  |
| `formSerialNumber` |  | nvarchar(50) | Y |  |
| `companyId` |  | nvarchar(50) | Y |  |
| `companyName` |  | nvarchar(250) | Y |  |
| `companyDB` |  | nvarchar(50) | Y |  |
| `creator` |  | nvarchar(50) | Y |  |
| `creatorName` |  | nvarchar(250) | Y |  |
| `applicant` |  | nvarchar(50) | Y |  |
| `applicantName` |  | nvarchar(250) | Y |  |
| `applicantDeptId` |  | nvarchar(50) | Y |  |
| `applicantDeptName` |  | nvarchar(250) | Y |  |
| `applicationDate` |  | datetime | Y |  |
| `accountDate` |  | datetime | Y |  |
| `applicantERPDeptId` |  | nvarchar(50) | Y |  |
| `applicantERPDeptName` |  | nvarchar(250) | Y |  |
| `ERPFormId` |  | nvarchar(50) | Y |  |
| `ERPFormName` |  | nvarchar(250) | Y |  |
| `costCenterCode` |  | nvarchar(50) | Y |  |
| `costCenterName` |  | nvarchar(250) | Y |  |
| `localCurrencyCode` |  | nvarchar(50) | Y |  |
| `localCurrencyName` |  | nvarchar(50) | Y |  |
| `localTotal` |  | decimal(21,6) | Y |  |
| `ERPFormSerailNumber` |  | nvarchar(50) | Y |  |
| `throwFailMessage` |  | nvarchar(max) | Y |  |
| `exchangeRate` |  | decimal(20,9) | Y |  |
| `vendorCode` |  | nvarchar(50) | Y |  |
| `vendorName` |  | nvarchar(250) | Y |  |
| `paymentCode` |  | nvarchar(50) | Y |  |
| `paymentName` |  | nvarchar(250) | Y |  |
| `invoiceType` |  | nvarchar(50) | Y |  |
| `invoiceTypeName` |  | nvarchar(250) | Y |  |
| `taxCode` |  | nvarchar(50) | Y |  |
| `taxName` |  | nvarchar(250) | Y |  |
| `taxPercentage` |  | nvarchar(50) | Y |  |
| `txtTax` |  | decimal(21,6) | Y |  |
| `remark` |  | nvarchar(max) | Y |  |
| `totalAmountUnTaxed` |  | decimal(21,6) | Y |  |
| `totalTax` |  | decimal(21,6) | Y |  |
| `totalAmountWithTax` |  | decimal(21,6) | Y |  |
| `localTotalAmountUnTaxed` |  | decimal(21,6) | Y |  |
| `localTotalTax` |  | decimal(21,6) | Y |  |
| `localTotalAmountWithTax` |  | decimal(21,6) | Y |  |
| `currencyCode` |  | nvarchar(50) | Y |  |
| `currencyName` |  | nvarchar(50) | Y |  |
| `total` |  | decimal(21,6) | Y |  |
| `sellersTaxIdNumber2` |  | nvarchar(50) | Y |  |
| `invoiceNumber2` |  | nvarchar(500) | Y |  |
| `certificateDate2` |  | datetime | Y |  |
| `deduction` |  | nvarchar(1) | Y |  |
| `deductionName` |  | nvarchar(50) | Y |  |
| `invoicePayment` |  | decimal(21,6) | Y |  |
| `invoiceTax` |  | decimal(21,6) | Y |  |
| `invoiceTaxable` |  | decimal(21,6) | Y |  |
| `invoiceTaxFree` |  | decimal(21,6) | Y |  |

#### `EPM_VendorRequestForm_CM_grid` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nvarchar(35) | N | PK |
| `formSerialNumber` |  | nvarchar(50) | Y |  |
| `serialNo` |  | nvarchar(4) | Y |  |
| `expenseDept_txt` |  | nvarchar(50) | Y |  |
| `expenseDept_lbl` |  | nvarchar(250) | Y |  |
| `categoryCode_txt` |  | nvarchar(50) | Y |  |
| `categoryCode_lbl` |  | nvarchar(50) | Y |  |
| `ERPCategoryCode_txt` |  | nvarchar(50) | Y |  |
| `ERPCategoryCode_lbl` |  | nvarchar(50) | Y |  |
| `accountCodeWindow_txt` |  | nvarchar(50) | Y |  |
| `accountCodeWindow_lbl` |  | nvarchar(50) | Y |  |
| `amount` |  | decimal(21,6) | Y |  |
| `amountUnTaxed` |  | decimal(21,6) | Y |  |
| `tax` |  | decimal(21,6) | Y |  |
| `amountWithTax` |  | decimal(21,6) | Y |  |
| `localAmountUnTaxed` |  | decimal(21,6) | Y |  |
| `localTax` |  | decimal(21,6) | Y |  |
| `localAmountWithTax` |  | decimal(21,6) | Y |  |
| `projectCode2_txt` |  | nvarchar(50) | Y |  |
| `projectCode2_lbl` |  | nvarchar(250) | Y |  |
| `remark2` |  | nvarchar(max) | Y |  |
| `source` |  | nvarchar(1) | Y |  |
| `sourceName` |  | nvarchar(50) | Y |  |
| `acp75formno` |  | nvarchar(50) | Y |  |
| `productTax` |  | nvarchar(10) | Y |  |
| `productTaxName` |  | nvarchar(10) | Y |  |

#### `EPM_VendorRequestForm_grid` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nvarchar(35) | N | PK |
| `formSerialNumber` |  | nvarchar(50) | Y |  |
| `serialNo` |  | nvarchar(4) | Y |  |
| `categoryCode_txt` |  | nvarchar(50) | Y |  |
| `categoryCode_lbl` |  | nvarchar(50) | Y |  |
| `certificateDate_txt` |  | datetime | Y |  |
| `amount` |  | decimal(21,6) | Y |  |
| `invoiceNumber` |  | nvarchar(500) | Y |  |
| `sellersTaxIdNumber` |  | nvarchar(50) | Y |  |
| `itemCode_txt` |  | nvarchar(80) | Y |  |
| `itemName` |  | nvarchar(120) | Y |  |
| `qty` |  | decimal(15,3) | Y |  |
| `taxCode2` |  | nvarchar(50) | Y |  |
| `taxName2` |  | nvarchar(50) | Y |  |
| `amountUnTaxed` |  | decimal(21,6) | Y |  |
| `tax` |  | decimal(21,6) | Y |  |
| `amountWithTax` |  | decimal(21,6) | Y |  |
| `localAmountUnTaxed` |  | decimal(21,6) | Y |  |
| `localTax` |  | decimal(21,6) | Y |  |
| `localAmountWithTax` |  | decimal(21,6) | Y |  |
| `projectCode2_txt` |  | nvarchar(50) | Y |  |
| `projectCode2_lbl` |  | nvarchar(250) | Y |  |
| `WBSCode_txt` |  | nvarchar(50) | Y |  |
| `WBSCode_lbl` |  | nvarchar(250) | Y |  |
| `remark2` |  | nvarchar(max) | Y |  |
| `period` |  | decimal(2,0) | Y |  |
| `source` |  | nvarchar(1) | Y |  |
| `sourceName` |  | nvarchar(50) | Y |  |
| `acp75formno` |  | nvarchar(50) | Y |  |
| `budgetPeriod` |  | nvarchar(10) | Y |  |

#### `EPM_VendorRequestForm_grid2` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nvarchar(255) | N | PK |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `gInvoiceItem` |  | nvarchar(255) | Y |  |
| `gItem` |  | nvarchar(255) | Y |  |
| `gApplicantERPDeptId` |  | nvarchar(255) | Y |  |
| `gApplicantERPDeptName` |  | nvarchar(255) | Y |  |
| `gAmount` |  | nvarchar(255) | Y |  |
| `gAmountUnTaxed` |  | nvarchar(255) | Y |  |
| `gTax` |  | nvarchar(255) | Y |  |
| `gLocalAmount` |  | nvarchar(255) | Y |  |
| `gLocalAmountUnTaxed` |  | nvarchar(255) | Y |  |
| `gLocalTax` |  | nvarchar(255) | Y |  |
| `gAccountCode` |  | nvarchar(255) | Y |  |
| `reasonCode` |  | nvarchar(50) | Y |  |
| `reasonName` |  | nvarchar(50) | Y |  |

### 前綴 `Ser` — 服務(Service)（13 表）


#### `Server2FavoriteMenu` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nvarchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `userOID` |  | nvarchar(32) | N |  |
| `menuMark` |  | nvarchar(100) | N |  |
| `accessType` |  | nvarchar(50) | N |  |
| `isMain` |  | int | N |  |
| `sequence` |  | int | N |  |

#### `Server2FavoriteProcess` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nvarchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `userOID` |  | nvarchar(32) | N |  |
| `processID` |  | nvarchar(32) | N |  |
| `sequence` |  | int | N |  |

#### `Server2NoticeWorkItem` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `workAssignmentOID` |  | nchar(32) | N |  |
| `workItemOID` |  | nchar(32) | N |  |
| `userOID` |  | nchar(32) | N |  |
| `bundleContainer` |  | ntext | N |  |
| `subject` |  | ntext | N |  |
| `processInstanceName` |  | nvarchar(100) | N |  |
| `createdTime` |  | datetime | N |  |
| `lvlValue` |  | int | N |  |
| `isView` |  | nvarchar(1) | N |  |

#### `Server2PackageInvokeAuthority` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | char(32) | N | PK |
| `userList` |  | ntext | Y |  |
| `organizationUnitList` |  | ntext | Y |  |
| `objectVersion` |  | int | N |  |
| `groupList` |  | ntext | Y |  |
| `functionDefList` |  | ntext | Y |  |

#### `Server2ProcessDefinition` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | char(32) | N | PK |
| `accessLevel` |  | nvarchar(50) | N |  |
| `id` |  | nvarchar(100) | N |  |
| `headerOID` |  | char(32) | N |  |
| `processDefinitionName` |  | nvarchar(100) | Y |  |
| `objectVersion` |  | int | N |  |
| `redefinableHeaderOID` |  | char(32) | Y |  |
| `applyDefaultNoticeContent` |  | int | N |  |
| `relationManDefId` |  | nvarchar(100) | Y |  |
| `lastActivityIdNum` |  | int | N |  |
| `lastActivitySetIdNum` |  | int | N |  |
| `lastTransitionIdNum` |  | int | N |  |
| `lastParticipantIdNum` |  | int | N |  |
| `lastFormalParameterIdNum` |  | int | N |  |
| `allowCanceled` |  | int | N |  |
| `notificationIntervalTimeUnit` |  | nvarchar(50) | N |  |
| `multiNotificationIntervalTime` |  | int | N |  |
| `multiNotification` |  | int | N |  |
| `actionAfterAbortedOID` |  | char(32) | Y |  |
| `actionAfterTerminatedOID` |  | char(32) | Y |  |
| `actionAfterCompletedOID` |  | char(32) | Y |  |
| `processViewInformationOID` |  | char(32) | Y |  |
| `abortable` |  | int | N |  |
| `bundleContainer` |  | ntext | Y |  |
| `noticable` |  | int | N |  |
| `noticeAllAuthority` |  | int | N |  |
| `additionalRules` |  | int | N |  |
| `personalDataProtection` |  | int | N |  |

#### `Server2ProcessDefinitionHeader` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | char(32) | N | PK |
| `createdTime` |  | datetime | N |  |
| `description` |  | ntext | Y |  |
| `durationUnit` |  | nvarchar(50) | Y |  |
| `limits` |  | real | Y |  |
| `priority` |  | nvarchar(50) | Y |  |
| `timeEstimationOID` |  | char(32) | Y |  |
| `validFrom` |  | datetime | Y |  |
| `objectVersion` |  | int | N |  |
| `validTo` |  | datetime | Y |  |
| `limitTemplate` |  | nvarchar(255) | Y |  |

#### `Server2ProcessPackage` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | char(32) | N | PK |
| `conformanceClassOID` |  | char(32) | Y |  |
| `headerOID` |  | char(32) | N |  |
| `id` |  | nvarchar(100) | N |  |
| `processPackageName` |  | nvarchar(100) | Y |  |
| `redefinableHeaderOID` |  | char(32) | N |  |
| `objectVersion` |  | int | N |  |
| `scriptDefinitionOID` |  | char(32) | Y |  |
| `containerOID` |  | char(32) | N |  |
| `firstActIsReqstPerform` |  | int | N |  |
| `packageInvokeAuthorityOID` |  | char(32) | Y |  |
| `mainProcessDefinitionId` |  | nvarchar(100) | Y |  |
| `userDefineMode` |  | nvarchar(50) | N |  |
| `userInputSubject` |  | int | N |  |
| `subjectTemplet` |  | nvarchar(1000) | Y |  |
| `bundleContainer` |  | ntext | Y |  |
| `formInstanceType` |  | int | N |  |

#### `Server2ProcessPackageCategory` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | char(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `packageCategoryName` |  | nvarchar(100) | N |  |

#### `Server2ProcessPackageCmItem` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | char(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `checkInTime` |  | datetime | Y |  |
| `checkoutTime` |  | datetime | Y |  |
| `checkoutUserOID` |  | char(32) | Y |  |
| `id` |  | nvarchar(100) | N |  |
| `lastVersion` |  | int | N |  |
| `categoryOID` |  | char(32) | Y |  |

#### `Server2ProcessPackageHeader` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | char(32) | N | PK |
| `costUnit` |  | nvarchar(50) | Y |  |
| `createdTime` |  | datetime | N |  |
| `description` |  | ntext | Y |  |
| `documentation` |  | nvarchar(100) | Y |  |
| `priorityUnit` |  | nvarchar(50) | Y |  |
| `vendor` |  | nvarchar(50) | N |  |
| `objectVersion` |  | int | N |  |
| `xpdlVersion` |  | nvarchar(10) | N |  |

#### `Server2ProcessPkg_ProcessDef` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `ProcessPackageOID` |  | char(32) | N | PK |
| `ProcessDefinitionOID` |  | char(32) | N | PK |

#### `Server2RedefinableHeader` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | char(32) | N | PK |
| `authorName` |  | nvarchar(100) | Y |  |
| `codePage` |  | nvarchar(50) | Y |  |
| `countryKey` |  | nvarchar(50) | Y |  |
| `publicationStatus` |  | nvarchar(50) | N |  |
| `objectVersion` |  | int | N |  |
| `version` |  | int | N |  |

#### `Server2ToDoWorkItem` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `workAssignmentOID` |  | nchar(32) | N |  |
| `workItemOID` |  | nchar(32) | N |  |
| `userOID` |  | nchar(32) | N |  |
| `bundleContainer` |  | ntext | N |  |
| `subject` |  | ntext | N |  |
| `processInstanceName` |  | nvarchar(100) | N |  |
| `createdTime` |  | datetime | N |  |
| `lvlValue` |  | int | N |  |

### 前綴 `Run` — —（1 表）


#### `RuntimePlatform` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `platformId` |  | nvarchar(100) | N |  |
| `platformName` |  | nvarchar(255) | N |  |
| `description` |  | nvarchar(1000) | Y |  |
| `bundleContainer` |  | ntext | Y |  |

### 前綴 `Err` — —（1 表）


#### `ErrorCombineServiceRecord` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `containerOID` |  | nchar(32) | N |  |
| `responseXml` |  | ntext | N |  |

### 前綴 `Wri` — —（1 表）


#### `WriteBackRecord` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `processSerialNumber` |  | nvarchar(100) | N |  |
| `dispatchType` |  | int | N |  |
| `createdTime` |  | datetime | N |  |
| `systemKey` |  | nvarchar(255) | Y |  |

### 前綴 `Mul` — —（2 表）


#### `MultiAPIconSwitch` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `userOID` |  | nchar(32) | N |  |
| `serverName` |  | nvarchar(30) | N |  |

#### `MultiProcessRefRecord` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `sourceBpmWFSerialNumber` |  | nvarchar(100) | Y |  |
| `bpmWFSerialNumber` |  | nvarchar(100) | Y |  |
| `bpmWFState` |  | int | Y |  |
| `bpmSFState` |  | int | Y |  |
| `bpmWorkItemOID` |  | nchar(32) | Y |  |
| `bpmSFSerialNumber` |  | nvarchar(100) | Y |  |
| `docKey` |  | nvarchar(255) | Y |  |
| `docPropId` |  | nvarchar(255) | Y |  |
| `formId` |  | nvarchar(255) | Y |  |
| `refId` |  | nvarchar(255) | Y |  |
| `performerId` |  | nchar(32) | Y |  |

### 前綴 `Acc` — —（1 表）


#### `AccessRightEntity` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `showPosition` |  | int | N |  |
| `containerOID` |  | nchar(32) | N |  |
| `securityLevelOID` |  | nchar(32) | N |  |
| `ownerOID` |  | nchar(32) | N |  |
| `accessType` |  | int | N |  |
| `noticeUserOID` |  | nchar(32) | Y |  |
| `isIncludeSubUnit` |  | int | Y |  |

### 前綴 `Rep` — —（3 表）


#### `ReportDefinition` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `reportUpDefOID` |  | nchar(32) | N |  |
| `formulateStaffOID` |  | nchar(32) | N |  |
| `processDefinitionId` |  | nvarchar(100) | N |  |
| `formDefinitionOID` |  | nchar(32) | N |  |
| `formDefinitionId` |  | nvarchar(100) | Y |  |
| `formDefinitionVer` |  | int | N |  |
| `createdTime` |  | datetime | N |  |
| `type` |  | int | Y |  |
| `status` |  | int | Y |  |
| `releaseTime` |  | datetime | Y |  |

#### `ReportDesignerDefinition` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `formSqlClauseOID` |  | nvarchar(32) | Y |  |
| `sqlConditionLists` |  | ntext | Y |  |
| `reportLists` |  | nvarchar(2000) | Y |  |
| `moduleDefinitionOID` |  | nvarchar(32) | Y |  |
| `programDefinitionId` |  | nvarchar(100) | Y |  |

#### `ReportUploadDefinition` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `reportID` |  | nvarchar(100) | N |  |
| `reportName` |  | nvarchar(100) | N |  |
| `reportDescription` |  | nvarchar(255) | Y |  |

### 前綴 `Sim` — —（1 表）


#### `SimulationInformation` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `cost` |  | nvarchar(50) | N |  |
| `timeEstimationOID` |  | nchar(32) | N |  |
| `objectVersion` |  | int | N |  |
| `instantiationType` |  | nvarchar(50) | N |  |

### 前綴 `ByV` — —（1 表）


#### `ByValueParameter` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `containerOID` |  | nchar(32) | N |  |
| `id` |  | nvarchar(100) | N |  |
| `objectVersion` |  | int | N |  |
| `valueOID` |  | nchar(32) | Y |  |
| `dataTypeOID` |  | char(32) | N |  |

### 前綴 `ByR` — —（1 表）


#### `ByReferenceParameter` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `containerOID` |  | nchar(32) | N |  |
| `id` |  | nvarchar(100) | N |  |
| `objectVersion` |  | int | N |  |
| `relevantDataOID` |  | nchar(32) | N |  |

### 前綴 `Scr` — —（2 表）


#### `ScriptDefinition` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `grammar` |  | nvarchar(100) | Y |  |
| `scriptDefinitionType` |  | nvarchar(50) | N |  |
| `objectVersion` |  | int | N |  |
| `version` |  | nvarchar(10) | Y |  |

#### `ScriptingApplication` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | char(32) | N | PK |
| `objectVersion` |  | int | Y |  |
| `scriptLanguage` |  | nvarchar(20) | Y |  |
| `script` |  | ntext | Y |  |
| `id` |  | nvarchar(100) | N |  |
| `applicationDefinitionName` |  | nvarchar(100) | Y |  |
| `externalReferenceOID` |  | char(32) | Y |  |
| `description` |  | ntext | Y |  |
| `isDefault` |  | int | N |  |
| `globalApplication` |  | int | Y |  |

### 前綴 `Dep` — —（2 表）


#### `DeployDocServer` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `deployedTime` |  | datetime | Y |  |
| `deployStatus` |  | nvarchar(50) | N |  |
| `docServerOID` |  | nchar(32) | N |  |
| `documentOID` |  | nchar(32) | N |  |
| `undeployedTime` |  | datetime | Y |  |
| `isCreatedServer` |  | int | N |  |

#### `DeployedUnit` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `orgUnitOID` |  | nchar(32) | N |  |
| `documentOID` |  | nchar(32) | N |  |
| `roleDefOID` |  | nchar(32) | N |  |
| `unitType` |  | nvarchar(50) | N |  |

### 前綴 `Tem` — —（1 表）


#### `TemplateGenMappingData` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `tiptopCompanyId` |  | nvarchar(100) | N |  |
| `tiptopDocPropId` |  | nvarchar(100) | N |  |
| `tiptopFormId` |  | nvarchar(100) | N |  |
| `templateId` |  | nvarchar(100) | N |  |
| `processPackageId` |  | nvarchar(100) | N |  |
| `isTemplateReference` |  | int | N |  |

### 前綴 `Sch` — —（1 表）


#### `SchemaType` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `content` |  | ntext | N |  |
| `elementName` |  | nvarchar(50) | Y |  |
| `typeName` |  | nvarchar(50) | Y |  |

### 前綴 `Sav` — —（1 表）


#### `SaveAsTemp` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `saveUserOID` |  | nchar(32) | N |  |
| `processPackageOID` |  | nchar(32) | N |  |
| `objectVersion` |  | int | N |  |
| `createdTime` |  | datetime | N |  |
| `categoryOID` |  | nchar(32) | Y |  |
| `processPackageId` |  | nvarchar(100) | N |  |
| `processPackageName` |  | nvarchar(100) | Y |  |
| `flowType` |  | nvarchar(30) | Y |  |

### 前綴 `EBG` — —（6 表）


#### `EBGForm` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `hdnJobId` |  | nvarchar(255) | Y |  |
| `processSerialNumber` |  | nvarchar(255) | Y |  |
| `applicant2` |  | nvarchar(255) | Y |  |
| `hdnSignerId` |  | nvarchar(255) | Y |  |
| `signStatus` |  | nvarchar(255) | Y |  |
| `remark` |  | nvarchar(255) | Y |  |
| `signDate` |  | nvarchar(255) | Y |  |
| `tradeItem` |  | nvarchar(255) | Y |  |
| `hdnUploadDocName` |  | nvarchar(255) | Y |  |
| `ebgOrder` |  | nvarchar(255) | Y |  |
| `signerName` |  | nvarchar(255) | Y |  |
| `hdnFormInstOID` |  | nvarchar(255) | Y |  |
| `applicantDate` |  | nvarchar(255) | Y |  |
| `isMailOTP` |  | nvarchar(255) | Y |  |
| `isExcuteSign` |  | nvarchar(255) | Y |  |
| `hdnAttachArray` |  | nvarchar(255) | Y |  |
| `hdnGetSignSuccess` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `email` |  | nvarchar(255) | Y |  |
| `hdnSVSName` |  | nvarchar(255) | Y |  |
| `schStatus` |  | nvarchar(255) | Y |  |
| `hdnTemplateId` |  | nvarchar(255) | Y |  |
| `fileSource` |  | nvarchar(255) | Y |  |
| `schMsg` |  | nvarchar(255) | Y |  |
| `signFilePDFName` |  | nvarchar(255) | Y |  |
| `OID` |  | nvarchar(255) | N | PK |
| `applicantUnit` |  | nvarchar(255) | Y |  |
| `signValidDay` |  | nvarchar(255) | Y |  |
| `vendorName` |  | nvarchar(255) | Y |  |
| `rdoChooseUpload` |  | nvarchar(255) | Y |  |
| `hdnProcessInstOID` |  | nvarchar(255) | Y |  |
| `applicant` |  | nvarchar(255) | Y |  |
| `sourceNum` |  | nvarchar(255) | Y |  |
| `objProp` |  | nvarchar(255) | Y |  |
| `hdnDocId` |  | nvarchar(255) | Y |  |
| `fileSource2` |  | nvarchar(255) | Y |  |
| `emailLocale` |  | nvarchar(255) | Y |  |
| `signerId` |  | nvarchar(255) | Y |  |
| `directions` |  | nvarchar(255) | Y |  |
| `applicantUnit2` |  | nvarchar(255) | Y |  |
| `filler` |  | nvarchar(255) | Y |  |
| `mailMessage` |  | nvarchar(255) | Y |  |
| `schTime` |  | nvarchar(255) | Y |  |

#### `EBGForm_templateGrid` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nvarchar(255) | N | PK |
| `signDate` |  | nvarchar(255) | Y |  |
| `signValidDay` |  | nvarchar(255) | Y |  |
| `ebgOrder` |  | nvarchar(255) | Y |  |
| `signerName` |  | nvarchar(255) | Y |  |
| `objProp` |  | nvarchar(255) | Y |  |
| `isMailOTP` |  | nvarchar(255) | Y |  |
| `emailLocale` |  | nvarchar(255) | Y |  |
| `signerId` |  | nvarchar(255) | Y |  |
| `directions` |  | nvarchar(255) | Y |  |
| `mailMessage` |  | nvarchar(255) | Y |  |
| `formSerialNumber` |  | nvarchar(255) | Y |  |
| `email` |  | nvarchar(255) | Y |  |

#### `EBGHistoricalSigner` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `userId` |  | nvarchar(100) | Y |  |
| `signerId` |  | nvarchar(100) | Y |  |
| `signerName` |  | nvarchar(100) | Y |  |
| `ebgFormOID` |  | nchar(32) | Y |  |
| `processSerialNumber` |  | nvarchar(100) | Y |  |
| `formSerialNumber` |  | nvarchar(100) | Y |  |
| `createdTime` |  | datetime | Y |  |

#### `EBGPropertise` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | Y |  |
| `vendorName` |  | nvarchar(10) | Y |  |
| `orgId` |  | nvarchar(255) | Y |  |
| `vendorUrl` |  | nvarchar(255) | Y |  |
| `isEnabledEbgVendor` |  | nvarchar(10) | Y |  |
| `account` |  | nvarchar(255) | Y |  |
| `password` |  | nvarchar(255) | Y |  |
| `svsUrl` |  | nvarchar(4000) | Y |  |
| `cloudStorDays` |  | nvarchar(10) | Y |  |

#### `EBGSignerTemplate` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `templateId` |  | nvarchar(255) | Y |  |
| `templateName` |  | nvarchar(255) | Y |  |
| `creatorOID` |  | nchar(32) | Y |  |
| `updaterOID` |  | nchar(32) | Y |  |
| `createdTime` |  | datetime | Y |  |
| `updateTime` |  | datetime | Y |  |
| `objectVersion` |  | int | N |  |

#### `EBGSignerTemplate_Users` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `ebgTemplateOID` |  | nchar(32) | Y |  |
| `signerOID` |  | nchar(32) | Y |  |
| `ebgOrder` |  | nvarchar(255) | Y |  |
| `description` |  | nvarchar(255) | Y |  |
| `objectVersion` |  | int | N |  |

### 前綴 `Wra` — —（4 表）


#### `WrapBamActInstData` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `limits` |  | real | N |  |
| `isOverTime` |  | int | N |  |
| `processInstanceOID` |  | nchar(32) | N |  |
| `mainProcessInstanceOID` |  | nchar(32) | N |  |
| `activityInstanceOID` |  | nchar(32) | N |  |
| `activityId` |  | nvarchar(100) | N |  |
| `activityName` |  | nvarchar(100) | N |  |
| `mainProcessId` |  | nvarchar(100) | N |  |
| `processId` |  | nvarchar(100) | N |  |
| `createdTime` |  | datetime | N |  |
| `startTime` |  | datetime | N |  |
| `endTime` |  | datetime | N |  |
| `actType` |  | nvarchar(20) | N |  |
| `dealTime` |  | real | N |  |
| `actualDealTime` |  | real | N |  |

#### `WrapBamProInstData` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `isMain` |  | int | N |  |
| `processId` |  | nvarchar(100) | N |  |
| `processInstanceOID` |  | nchar(32) | N |  |
| `mainProcessId` |  | nvarchar(100) | N |  |
| `mainProcessInstanceOID` |  | nchar(32) | N |  |
| `createdTime` |  | datetime | N |  |
| `endTime` |  | datetime | Y |  |
| `subject` |  | ntext | Y |  |
| `requesterOID` |  | nchar(32) | Y |  |
| `requesterId` |  | nvarchar(100) | Y |  |
| `requesterName` |  | nvarchar(100) | Y |  |
| `invokeOrganizationUnitOID` |  | nchar(32) | Y |  |
| `invokeOrganizationUnitId` |  | nvarchar(100) | Y |  |
| `invokeOrganizationUnitName` |  | nvarchar(100) | Y |  |
| `currentState` |  | int | N |  |
| `limits` |  | real | Y |  |
| `serialNumber` |  | nvarchar(100) | Y |  |
| `isOverTime` |  | int | N |  |
| `dealTime` |  | real | Y |  |
| `actualDealTime` |  | real | Y |  |

#### `WrapBamWorkAssignmentData` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `limits` |  | real | N |  |
| `createdTime` |  | datetime | N |  |
| `startTime` |  | datetime | Y |  |
| `workAssignmentOID` |  | nchar(32) | N |  |
| `workItemOID` |  | nchar(32) | N |  |
| `workItemName` |  | nvarchar(100) | N |  |
| `performerOID` |  | nchar(32) | N |  |
| `userId` |  | nvarchar(100) | N |  |
| `userName` |  | nvarchar(100) | N |  |
| `orgUnitId` |  | nvarchar(100) | N |  |
| `mainOUDOID` |  | nchar(32) | N |  |
| `organizationUnitName` |  | nvarchar(100) | N |  |
| `processId` |  | nvarchar(100) | N |  |
| `mainProcessId` |  | nvarchar(100) | N |  |
| `processInstanceOID` |  | nchar(32) | N |  |
| `mainProcessInstanceOID` |  | nchar(32) | N |  |
| `subject` |  | ntext | Y |  |
| `serialNumber` |  | nvarchar(100) | Y |  |
| `activityInstanceOID` |  | nchar(32) | N |  |
| `activityDefinitionId` |  | nvarchar(100) | N |  |
| `activityName` |  | nvarchar(100) | Y |  |

#### `WrapBamWorkItemData` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `limits` |  | real | N |  |
| `createdTime` |  | datetime | N |  |
| `startTime` |  | datetime | N |  |
| `endTime` |  | datetime | N |  |
| `workItemOID` |  | nchar(32) | N |  |
| `workItemName` |  | nvarchar(100) | N |  |
| `performerOID` |  | nchar(32) | N |  |
| `userId` |  | nvarchar(100) | N |  |
| `userName` |  | nvarchar(100) | N |  |
| `orgUnitId` |  | nvarchar(100) | N |  |
| `mainOUDOID` |  | nchar(32) | N |  |
| `organizationUnitName` |  | nvarchar(100) | N |  |
| `processInstanceOID` |  | nchar(32) | N |  |
| `mainProcessInstanceOID` |  | nchar(32) | N |  |
| `processId` |  | nvarchar(100) | N |  |
| `mainProcessId` |  | nvarchar(100) | N |  |
| `isOverTime` |  | int | N |  |
| `activityInstanceOID` |  | nchar(32) | N |  |
| `activityDefinitionId` |  | nvarchar(100) | N |  |
| `activityName` |  | nvarchar(100) | N |  |
| `dealTime` |  | real | N |  |
| `actualDealTime` |  | real | N |  |

### 前綴 `Ann` — —（5 表）


#### `AnnouncementAttachment` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | char(32) | N |  |
| `objectVersion` |  | int | N |  |
| `AnnounceAttachmentName` |  | nvarchar(128) | N |  |
| `AnnounceAttachmentFileType` |  | nvarchar(32) | N |  |
| `AnnounceAttachmentFileName` |  | nvarchar(128) | Y |  |
| `AnnounceAttachmentContent` |  | text | Y |  |
| `AnnouncementOID` |  | char(32) | N |  |
| `AnnouncementDefault` |  | int | N |  |
| `AnnounceAttachmentType` |  | int | N |  |
| `AnnounceAttachmentCreateTime` |  | datetime | N |  |

#### `AnnouncementData` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | char(32) | N |  |
| `objectVersion` |  | int | N |  |
| `AnnouncementTitle` |  | nvarchar(256) | N |  |
| `AnnouncementContent` |  | text | N |  |
| `AnnouncementPublishTime` |  | datetime | N |  |
| `AnnouncementTopTime` |  | datetime | Y |  |
| `AnnouncementValidTime` |  | datetime | N |  |
| `AnnouncementCreateTime` |  | datetime | N |  |
| `AnnouncementPublisherOID` |  | char(32) | N |  |
| `AnnouncementDepartmentOID` |  | char(32) | N |  |
| `AnnouncementEmergency` |  | char(32) | N |  |
| `AnnouncementType` |  | char(32) | N |  |
| `AnnouncementPermission` |  | int | N |  |

#### `AnnouncementEmergency` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | char(32) | N |  |
| `objectVersion` |  | int | N |  |
| `AnnouncementEmergencyName` |  | nvarchar(64) | N |  |

#### `AnnouncementRecords` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | char(32) | N |  |
| `objectVersion` |  | int | N |  |
| `RecordsUserOID` |  | char(32) | N |  |
| `RecordsDepartmentOID` |  | char(32) | N |  |
| `AnnouncementOID` |  | char(32) | N |  |
| `AnnouncementRecordsCount` |  | int | N |  |
| `AnnouncementRecordsCreateTime` |  | datetime | N |  |

#### `AnnouncementType` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | char(32) | N |  |
| `objectVersion` |  | int | N |  |
| `AnnouncementTypeName` |  | nvarchar(64) | N |  |

### 前綴 `Ass` — —（1 表）


#### `AssignmentNoPerPerson` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `containerOID` |  | nchar(32) | N |  |
| `userOID` |  | nchar(32) | N |  |
| `assignmentNo` |  | int | N |  |

### 前綴 `Onl` — —（1 表）


#### `OnlineReadWatermarkPattern` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | Y |  |
| `watermarkId` |  | nvarchar(50) | N |  |
| `watermarkContext` |  | nvarchar(4000) | Y |  |
| `watermarkAttribute` |  | nvarchar(300) | Y |  |
| `readwatermarkContext` |  | nvarchar(4000) | Y |  |
| `readwatermarkAttribute` |  | nvarchar(300) | Y |  |

### 前綴 `Vip` — —（1 表）


#### `VipUsers` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `userOID` |  | nvarchar(32) | N | PK |

### 前綴 `Wat` — —（1 表）


#### `WatermarkAllowedForm` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `formId` |  | nvarchar(256) | N |  |
| `containerOID` |  | nchar(32) | N |  |

### 前綴 `Abs` — —（1 表）


#### `AbsenceRecord` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `description` |  | ntext | Y |  |
| `endTime` |  | datetime | N |  |
| `ownerOID` |  | nchar(32) | Y |  |
| `objectVersion` |  | int | N |  |
| `startTime` |  | datetime | N |  |
| `absenceDay` |  | datetime | N |  |

### 前綴 `EFG` — —（1 表）


#### `EFGPIntePLMInfo` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `ProcessID` |  | nvarchar(50) | N |  |
| `ProcessInsOID` |  | nvarchar(50) | N |  |
| `ProcessSNO` |  | nvarchar(100) | N |  |
| `PLMSourceFormID` |  | nvarchar(50) | N |  |
| `PLMSourceFormNum` |  | nvarchar(50) | N |  |
| `hdnSourceFile` |  | nvarchar(4000) | Y |  |
| `SystemDate` |  | nvarchar(50) | N |  |

### 前綴 `Sap` — —（2 表）


#### `SapConnection` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `JCO_DEST` |  | nvarchar(50) | N | PK |
| `JCO_ASHOST` |  | nvarchar(50) | N |  |
| `JCO_SYSNR` |  | nvarchar(50) | N |  |
| `JCO_CLIENT` |  | nvarchar(50) | N |  |
| `JCO_USER` |  | nvarchar(50) | N |  |
| `JCO_PASSWD` |  | nvarchar(50) | N |  |
| `JCO_LANG` |  | nvarchar(50) | N |  |

#### `SapFormMapping` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nvarchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `isAjax` |  | int | N |  |
| `mappingId` |  | nvarchar(100) | N |  |
| `formDefId` |  | nvarchar(100) | N |  |
| `sapConnDest` |  | nvarchar(100) | N |  |
| `mappingXML` |  | nvarchar(max) | N |  |

### 前綴 `Rsr` — —（2 表）


#### `RsrcBundle` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `programId` |  | nvarchar(200) | N |  |
| `labelKey` |  | nvarchar(100) | N |  |

#### `RsrcBundleValue` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `containerOID` |  | nchar(32) | N |  |
| `languageOID` |  | nchar(32) | N |  |
| `programId` |  | nvarchar(200) | N |  |
| `labelKey` |  | nvarchar(100) | N |  |
| `labelValue` |  | nvarchar(500) | N |  |
| `labelHint` |  | nvarchar(1000) | Y |  |
| `description` |  | nvarchar(1000) | Y |  |

### 前綴 `WFR` — —（1 表）


#### `WFRequestRecordModel` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | char(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `senderIp` |  | nvarchar(255) | Y |  |
| `receiverIp` |  | nvarchar(255) | Y |  |
| `efSiteName` |  | nvarchar(255) | Y |  |
| `efLogonID` |  | nvarchar(255) | Y |  |
| `integratedSystemCode` |  | nvarchar(255) | Y |  |
| `organizationId` |  | nvarchar(255) | Y |  |
| `organizationUnitId` |  | nvarchar(255) | Y |  |
| `formCreatorId` |  | nvarchar(255) | Y |  |
| `formId` |  | nvarchar(255) | Y |  |
| `sourceFormKey` |  | nvarchar(500) | N |  |
| `processInstanceOID` |  | char(32) | N |  |
| `createTime` |  | datetime | N |  |
| `action` |  | nvarchar(5) | Y |  |

### 前綴 `Glo` — —（1 表）


#### `GlobalRelevantData` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `id` |  | nvarchar(100) | N |  |
| `objectVersion` |  | int | N |  |
| `valueOID` |  | nchar(32) | Y |  |
| `dataTypeOID` |  | nchar(32) | N |  |

### 前綴 `Rol` — —（2 表）


#### `Role` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `actorOID` |  | nchar(32) | N |  |
| `definitionOID` |  | nchar(32) | N |  |
| `organizationUnitOID` |  | nchar(32) | N |  |

#### `RoleDefinition` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `roleDefinitionName` |  | nvarchar(100) | N |  |
| `shortName` |  | nvarchar(100) | Y |  |
| `organizationOID` |  | nchar(32) | Y |  |
| `description` |  | ntext | Y |  |

### 前綴 `Del` — —（2 表）


#### `DeliveryProcessConfiguration` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `id` |  | nvarchar(100) | N |  |
| `frontProcessId` |  | nvarchar(100) | N |  |
| `backProcessId` |  | nvarchar(100) | N |  |
| `frontFormId` |  | nvarchar(100) | N |  |
| `backFormId` |  | nvarchar(100) | N |  |
| `requesterType` |  | int | N |  |
| `requesterFormField` |  | nvarchar(100) | Y |  |
| `requesterOID` |  | nchar(32) | Y |  |
| `requestOrgUnitType` |  | int | N |  |
| `requestOrgUnitFormField` |  | nvarchar(100) | Y |  |
| `formMapping` |  | ntext | Y |  |
| `createdTime` |  | datetime | Y |  |
| `updateTime` |  | datetime | Y |  |
| `creatorOID` |  | nchar(32) | Y |  |
| `updaterOID` |  | nchar(32) | Y |  |
| `terminalProcessState` |  | int | N |  |
| `abortProcessState` |  | int | N |  |
| `reexecuteProcessState` |  | int | N |  |
| `recallProcessState` |  | int | N |  |
| `isAttachDelivery` |  | int | Y |  |
| `isAttachByName` |  | int | Y |  |
| `attachName` |  | nvarchar(255) | Y |  |
| `isAttachByType` |  | int | Y |  |
| `attachType` |  | nvarchar(255) | Y |  |

#### `DeliveryProcessInstance` — （無中文名）　(列數約 0)

| 欄位 | 中文名/說明 | 型別 | 可空 | 鍵別 |
| --- | --- | --- | :-: | :-: |
| `OID` |  | nchar(32) | N | PK |
| `objectVersion` |  | int | N |  |
| `deliveryProcessConfigId` |  | nvarchar(100) | N |  |
| `frontProcessInstanceOID` |  | nchar(32) | N |  |
| `frontProcessSerialNo` |  | nvarchar(100) | Y |  |
| `backProcessInstanceOID` |  | nchar(32) | Y |  |
| `backProcessSerialNo` |  | nvarchar(100) | Y |  |
| `frontProcessId` |  | nvarchar(100) | N |  |
| `backProcessId` |  | nvarchar(100) | N |  |
| `frontFormId` |  | nvarchar(100) | N |  |
| `backFormId` |  | nvarchar(100) | N |  |
| `requesterType` |  | int | N |  |
| `requesterOID` |  | nchar(32) | Y |  |
| `requestOrgUnitType` |  | int | N |  |
| `requestOrgUnit` |  | nchar(32) | Y |  |
| `formMapping` |  | ntext | Y |  |
| `frontFormField` |  | ntext | Y |  |
| `backFormField` |  | ntext | Y |  |
| `invokeActivityId` |  | nvarchar(100) | Y |  |
| `aborted` |  | int | Y |  |
| `abortFailException` |  | ntext | Y |  |
| `ignoreAbortFail` |  | int | Y |  |
| `abortFailProcessed` |  | int | Y |  |
| `createdTime` |  | datetime | Y |  |
| `updateTime` |  | datetime | Y |  |
| `getDocState` |  | int | Y |  |