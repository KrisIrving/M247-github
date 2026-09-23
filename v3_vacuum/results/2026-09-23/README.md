# 2026-09-23 验证记录

## 结论

`T/TFinal=PBiCGStab+DILU` 可作为后续候选：官方 192,000 单元教程网格的 20 ps
启动回归中，12 个检查场与上游基线逐值完全相同，9 步时间步历史一致。这个
测试只覆盖 20 ps，并未完成官方 100 us 全教程。

温度和压力候选组合的纯 Ar 静止储库测试运行到 3 µs，共 30,019 步、检查 10
个输出时刻。按 0.2 mm 域长与 Ar 声速 682.584 m/s 估算，相当于约 10.24 个
声学穿越时间。所有方程零迭代上限命中；T 最多 28 次迭代，p_rgh[DICPCG]
最多 1 次。压力范围为 0.599999999991–0.600000000043 Pa，温度范围为
1343.14999998–1343.1500001 K，密度为 2.14628406437e-6 kg/m³，最大速度
2.15e-11 m/s；Ar/金属/蒸气体积分数保持 1/0/0。实际密度与理想气体预期值
之间约 9e-7 的相对差异在预设阈值内。

## 限制与后续

- PCG+DIC 仅在均匀、静止纯 Ar 储库中验证过；没有证据支持它对激光加热、蒸发
  和耦合流动中的压力矩阵仍合适。进入 V1 前须检查矩阵性质，或改用适用的求解器。
- 官方网格对照仅 20 ps 启动区间，因此完整默认教程回归仍为 PENDING。
- 尚未验证 HK 通量积分、潜热闭合、M247 合金物性、蒸气凹坑/熔道以及稀薄 Ar
  的真实流动。当前结果不能宣称真空 LPBF 物理模型完成。
- 没有新增/修改低压物理参数、HK 方程或经验反冲压力。

## 文件和复现

- `ten-acoustic-combined-fields.json`：3 µs 纯 Ar 场值范围与阈值结果。
- `ten-acoustic-combined-iterations.json`：按方程统计的 33 万余次压力解等求解器审计。
- `default-Tsolver-fields.json`：官方网格上游/温度求解器候选逐场差异。
- `combined-long-combined-iterations.json`、`combined-long-combined-fields.json`：20 ns
  初始组合求解器筛查。
- `../scripts/audit_solver_iterations.py LOG --json OUT`：复核求解器迭代上限。
- `../scripts/run_linear_solver_probe.sh LBF_DIR FRESH_OUTDIR`：纯 Ar 方程求解器对照。
  该脚本适用于受控数值诊断，不会改变物理模型。
- 官方网格短回归：设置 `V3_T_SOLVER_PROBE=1` 后运行
  `../validation/V0B_argon_smoke/prepare_default_regression.sh`；比较时给
  `compare_default_cases.py` 传 `--allow-fv-solution`，该选项只允许差异在求解器字典。

完整 OpenFOAM 日志保存在本机 WSL 验证目录，不纳入 Git，以免把大文件写入源码库。

### V1 平面蒸发

`../validation/V1_planar_evaporation/README.md` 记录了 HK 源项、液汽质量转移、潜热
关系以及网格/时间步/界面宽度/温度/压力敏感性。对应的 `v1-planar-*.json` 是小型
结构化报告；100 步结果明确标记 NEEDS_REVIEW，因为闭合反馈触发限幅。短时源项与
质量耦合通过不代表持续闭合稳定，也不代表已验证 M247 真空 LPBF。

