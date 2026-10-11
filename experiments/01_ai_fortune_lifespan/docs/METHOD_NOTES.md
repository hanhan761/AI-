# 冻结协议、实现与发布适配

config/v3/protocol.json 保留原始冻结文本，不能据此忽略后续执行变化：

1. 初始 workers=20；实际主生成与盲评在统一调度中调整为 30 并发。补跑亦为 30 并发。这里未启动任何新调用。
2. 原主分析只纳入 attempt n=1 且 state=done 的回答，不能解读为“任意次首个有效答案”。补充分析才使用跨批次每格首个有效回答。
3. 原请求 24 型号，准入 18；最后按可用性保留 15 个完整型号。另 3 个为 GLM-4.7、qwen3-max、qwen3-coder-plus；未根据准确率淘汰。
4. 常规 ambiguous 不自动重放；后续用户明确授权纯生成的 ambiguous 在独立批次重放。无原文或不能确认完成的旧调用仍不算有效答案，旧账本和主分析保留。
5. 固定打乱映射的 4 条记录跨出生队列，均保持同性别；源于构建器的单例回退。寿命排序统计仍严格在同性别、50 年队列内比较。此例外保留并公开，未为发布改动历史映射。
6. 自动评委为 qwen3.8-max 与 DeepSeek-V3-2；预设选取 32 名 AA 人物。主分析汇总中的评委结果按该报告冻结时点保留，不能假定全部来自生成首试或所有补跑均被重新盲评。
7. 主协议 source_limits 中“24 independent confirmations”是沿用的候选阶段措辞；正式主结果 18 路由，补充结果 15 路由。该条要表达的是同家族模型相关，并非独立确认。

## 公开代码适配

统计内核 research_stats.py、提示词 prompt.py、原主分析 analyze.py、盲评构建器 build_judges.py、断点队列 durable_queue.py 保留原实现。rebuild_dataset.py 从原构建器抽取实际使用的人物筛选/命盘/划分/打乱步骤，去掉已弃用的 v2 年龄分箱预测协议和旧任务构建；保留分箱标签仅用于数据描述。build.py 保留 v3 任务生成，去掉发布环境不适用的冻结清单重写。

analyze_supplemental.py 保留补充分析计算，仅将内部服务器路径改成命令行参数；导出的来源批次只保留编号。公开 JSON 去掉机器路径与运行细节，模型统计数值保持原值。docs/original_freeze_hashes.json 用于说明原始冻结文件的校验值，不要求发布适配后的源文件与历史哈希一致。

## 模型调用接口

driver.py 依赖已获授权的交晓智原生网关模块 remote_direct_gateway.RemoteDirectCaller，通过 BAZI_GATEWAY_DIR 指定其安装目录。该私有网关、账号与密钥不在此仓库中；公开包不保证未知机器上即装即用，也不会切换成其他 API 冒充本次实验。

在已有授权网关与本地重建输入的环境中，队列入口如下。新运行请用新目录，保留原账本：

~~~bash
python src/v3/durable_queue.py --tasks runs/v3/tasks.json --run-dir runs/new_experiment --driver driver:factory --workers 30 --max-attempts 2 --max-seconds 172800
~~~

成功完成不重发；权限失败熔断；ambiguous 默认不重放。此命令仅为复现实验接口说明，发布过程中未执行。全实验数据构建和模型调用需自行满足来源及接口授权。
