# 数据来源与可用性

来源：Astrodienst AG / Astrodatabank，C 首字母 XML 样本。2026-10-06 取得的文件为 c_sample_260919_1519.xml，归档 ZIP 的 SHA256 为 da4a0638434dad80f1ff028e3ac898c4a9e3d2f7bb4a665d2086d5c3770844e1。

- [来源下载入口](https://www.astro.com/adbexport/)
- [样本归档](https://www.astro.com/adbexport/c_sample.zip)
- [XML 格式说明](https://www.astro.com/astro-databank/Help:XML_export_format)

原始 XML 的 important_notice 明确将 research_data 中的关系、事件资料限定为研究用途，公开或分发需要权利人单独许可；来源笔记与传记另有版权。原文中的简短许可提示为：“Publication or distribution of these data is restricted and requires an individual permission by the copyright holder.”

本仓库因此公开模型层级统计汇总与分析代码，不镜像原始 XML、逐人寿命、事件、传记、名单、资料笔记、匿名命盘全集或可关联回人物的回答原文。匿名化本身不解除来源的再分发限制。理论文件是经典文本摘录/释义，保留逐条出处链接；不据此声称现代编辑内容的版权归本项目所有。

## 本地重建输入

取得并获准使用同版 XML 后，在实验目录执行：

~~~bash
python src/rebuild_dataset.py --xml /path/to/c_sample_260919_1519.xml
python src/v3/build.py
python tests/verify_local.py
~~~

data/v3 和 runs 目录被 .gitignore 排除。数据重建器沿用原始人物筛选、日柱约定、随机种子、分组与映射；同版数据应得到 2173 人、其中评价 1712 人。更新版来源不保证相同样本，不应冒充原实验。

若拥有完整本地队列账本，可执行以下补充分析命令：

~~~bash
python src/analyze_supplemental.py --ledgers original.sqlite3 retry1.sqlite3 retry2.sqlite3 retry_all.sqlite3 final_two.sqlite3 --out data/generated
~~~

这会使用同一个冻结解析器和统计实现重新计算，不会调用大模型。需要同时具备重建后的 data/v3 文件；账本内含逐人信息，不应上传。公开的汇总数据足以复画主图和核对汇总结论，不能替代原始记录开展任意新的人物级分析。

## 文件与单位

- model_results.csv：一致率与 CI 以百分数表示；配对差异以百分点表示。
- aggregate.json：mean、ci、coverage 用 0–1 比例；paired.mean/ci 是两条件的比例差，可为负。
- repeat_sd_mean：同人物重复寿夭分值的 SD 均值。
- n_people：有有效数值预测的人物数；planned_people 是群体基数。
- insufficient 和 identity_recognized 会降低数值预测覆盖率，但结构有效回答总数仍包括它们。
