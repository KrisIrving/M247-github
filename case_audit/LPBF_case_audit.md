# LPBF / LaserBeamFoam 算例审查报告

- 生成时间：2026-08-03T17:07:43+08:00
- 算例根目录：`/media/kris/one/M247/M247-github`
- Git revision：`bb16b35091536e3f0498325a9c20e0404a1d0b63`
- 审查脚本版本：1.1.0

## 1. 结论摘要

该算例使用约 **864,000** 个六面体单元、**224** 个最终粉末颗粒、激光半径 **43.000 μm**，在 **100.000 μs** 的时间窗内模拟扫描初始段。
自动检查得到：**HIGH 5 项、MEDIUM 11 项、LOW 3 项**。

最优先核验事项是：① `transformPoints` 后的激光位置/方向；② `controlDict` 求解器名称与实际命令；③ `initial/T`、`initial/Laser_boundary` 等 FoamFile.object 元数据；④ 粉末床堆积率与最终 PSD。

## 2. 运行流程与复现入口

- `controlDict.application`：`Flint_multiphaseEulerFoamD`
- Allrun 实际求解器：`laserbeamFoam`
- `startFrom`：`latestTime`
- 串行流程：复制 `initial` → `blockMesh` → `setSolidFraction` → `transformPoints` → `laserbeamFoam`。
- 粉末来源：`DEM_large/input.liggghts` 生成颗粒，最终 `constant/location` 被 `setSolidFraction` 读取。

## 3. 坐标系、几何与网格

- 旋转前网格范围：x=[0.000, 300.000] μm; y=[0.000, 1200.000] μm; z=[0.000, 300.000] μm
- 旋转后实际范围：x=[0.000, 300.000] μm; y=[-300.000, 0.000] μm; z=[0.000, 1200.000] μm
- `transformPoints` 旋转：([0.0, 1.0, 0.0], [0.0, 0.0, 1.0])
- 重力：[0.0, 9.81, 0.0] m/s²；激光入射向量：[0.0, 1.0, 0.0]
- block 单元数：[60, 240, 60]；总单元：864,000
- 旋转前单元尺寸：5.000 μm, 5.000 μm, 5.000 μm
- 激光直径跨越约 **17.2 个单元**；半径跨越约 8.6 个单元。

旋转 `(0,1,0) → (0,0,1)` 后，本算例的空间语义可读为：最终 **Y 为竖直方向**、最终 **Z 为扫描长方向**；边界名称不会因旋转自动改名，因此 `topWall`、`rightWall` 等名称应按实际几何位置解释，而不能只按名字解释。

## 4. 粉末床与 DEM 指标

- 最终颗粒数：**224**；location 时间步：750000
- 粒径（数量分布）：Dmin=32.500 μm，D10=32.500 μm，D50=42.500 μm，D90=52.500 μm，Dmax=67.500 μm
- 粒径（体积加权）：D10=37.500 μm，D50=47.500 μm，D90=62.500 μm
- 粉末质量：0.090964 mg；球体总体积：0.010652 mm³
- 截断区厚度：80.000 μm；该整个区间的固相体积分数：**0.3698**；孔隙率：**0.6302**
- 等效致密固体厚度：29.588 μm；check.py 目标层厚：50.000 μm；按目标层厚计算的表观堆积率：**0.5918**
- 若目标堆积率为 0.58，当前粉末量对应名义层厚：51.013 μm
- 颗粒顶部高度：P10=133.997 μm，P50=147.496 μm，P90=170.220 μm，最大=179.656 μm
- 相对基板顶面的颗粒顶部高度：P50=47.496 μm，P90=70.220 μm，最大=79.656 μm
- 接触重叠对数：334；最大几何重叠：0.013467 μm；最大重叠/较小半径：0.0513%
- DEM 时间步：5e-08 s；插入率：2e+05 1/s；insert_every=1000；名义每事件插入数=10
- 请求插入：1000；日志删除：776；最终保留：224；受限插入警告：110 次。
- DEM 接触模型：hertz tangential history；参数={'youngs_modulus_cgs': 50000000.0, 'poisson_ratio': 0.3, 'coefficient_restitution': 0.1, 'coefficient_friction': 0.1, 'gravity_cgs_cm_s2': 981.0}

最终离散粒径计数（μm → 颗粒数）：

```text
32.5: 42, 37.5: 69, 42.5: 24, 47.5: 41, 52.5: 28, 57.5: 3, 62.5: 13, 67.5: 4
```

## 5. 激光与工艺参数

- 激光半径/直径：43.000 μm / 86.000 μm
- 波长：1.0640 μm；电子数密度：5.83e+29 m⁻³
- `Radius_Flavour`=2.0；`N_sub_divisions`=1.0；`PowderSim`=true
- t=0 位置：(100.000, 20.000, 100.000) μm；t=endTime 位置：(100.000, 20.000, 200.000) μm
- t=0 功率：10 W；t=endTime 功率：350 W
- 名义扫描速度：1 m/s；本次模拟距离：100.000 μm
- 名义线能量 P/v：350 J/m（即 0.35 J/mm）
- 功率时间表在本次时间窗内积分能量：0.034998 J
- 轨迹移动定义到：1000.000 μs；算例 endTime：100.000 μs

说明：这里的“积分能量”是输入功率对时间的积分，不等于材料实际吸收能量；实际吸收还受光学模型、自由表面、反射和数值离散影响。

## 6. 材料与界面物性

- 金属：ρ=8540 kg/m³，ν=3.7e-07 m²/s，Tsolidus=1573 K，Tliquidus=1639 K，Lf=2.9e+05 J/kg
- 动力黏度 μ=ρν：0.0031598 Pa·s；熔化区间：66 K
- 导热系数多项式系数：[6.484, 0.012, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]；比热多项式系数：[376.4, 0.2, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
- 300 K：k=10.084 W/(m·K)，cp=436.4 J/(kg·K)，α=2.7058e-06 m²/s
- solidus：k=25.36 W/(m·K)，cp=691 J/(kg·K)；liquidus：k=26.152 W/(m·K)，cp=704.2 J/(kg·K)
- 表面张力 σ=1.75 N/m；dσ/dT=-1e-05 N/(m·K)
- 蒸发：Tvap=3186 K，Lv=6.3e+06 J/kg，p0=1e+05 Pa
- 气相：ρ=1 kg/m³，ν=1.48e-05 m²/s。

## 7. 时间推进、输出与并行设置

- endTime=100.000 μs；初始 Δt=1.000e-08 s；最大 Δt=1.000e-06 s
- maxCo=0.2；maxAlphaCo=0.2；writeInterval=25.000 μs
- 若始终使用初始 Δt，名义步数约 10000；实际步数由可调时间步决定。
- 并行域数：48；simple 分解 n=[6.0, 1.0, 8.0]；平均约 18000 cells/rank。
- 动量模型：laminar；PIMPLE={'nOuterCorrectors': 1.0, 'nCorrectors': 3.0, 'nNonOrthogonalCorrectors': 0.0}；alpha 控制={'nAlphaCorr': 2.0, 'nAlphaSubCycles': 1.0}
- 关键离散格式：U 对流=Gauss linearUpwind grad(U)；T 对流=Gauss upwind；alpha 对流=Gauss interfaceCompression vanLeer 1

## 8. 初始/边界条件概览

- `Laser_boundary`：object=`p_rgh`；internalField=`uniform 0`；边界=back:fixedValue, front:fixedValue, leftWall:fixedValue, rightWall:fixedValue, topWall:fixedValue, bottomWall:fixedValue, defaultFaces:empty
- `T`：object=`p_rgh`；internalField=`uniform 300.0`；边界=back:zeroGradient, front:zeroGradient, leftWall:zeroGradient, rightWall:zeroGradient, topWall:zeroGradient, bottomWall:zeroGradient, defaultFaces:zeroGradient
- `TRHS`：object=`TRHS`；internalField=`uniform 0`；边界=back:calculated, front:calculated, leftWall:calculated, rightWall:calculated, topWall:calculated, bottomWall:calculated
- `U`：object=`U`；internalField=`uniform (0 0 0)`；边界=leftWall:fixedValue, rightWall:fixedValue, bottomWall:fixedValue, topWall:pressureInletOutletVelocity, front:fixedValue, back:fixedValue
- `alpha.metal`：object=`alpha.metal`；internalField=`uniform 0`；边界=back:zeroGradient, front:zeroGradient, leftWall:zeroGradient, rightWall:zeroGradient, topWall:zeroGradient, bottomWall:zeroGradient
- `p_rgh`：object=`p_rgh`；internalField=`uniform 0`；边界=back:fixedFluxPressure, front:fixedFluxPressure, leftWall:fixedFluxPressure, rightWall:fixedFluxPressure, topWall:totalPressure, bottomWall:fixedFluxPressure, defaultFaces:empty

## 9. 自动发现的问题与建议

### 1. [HIGH] controlDict 的 application 与实际求解器不一致

**现象：** application=Flint_multiphaseEulerFoamD，Allrun 实际执行 laserbeamFoam。这会误导复现者，并可能影响依赖 application 字段的流程。

**建议：** 把 system/controlDict 中 application 改为 laserbeamFoam。

### 2. [HIGH] 默认从 latestTime 启动，容易意外续算旧结果

**现象：** Allrun 仅执行 cp -r initial 0，未先删除旧时间目录；若 0 已存在，复制语义也可能生成 0/initial。

**建议：** 在全新运行脚本中先清理 0 和数值时间目录，或改为 startFrom startTime；续算另设独立脚本。

### 3. [HIGH] 字段头部 object 名称错误：initial/Laser_boundary

**现象：** 文件名为 Laser_boundary，FoamFile.object 却为 p_rgh。

**建议：** 将 object 改为 Laser_boundary，随后运行 foamDictionary/求解器启动检查。

### 4. [HIGH] 字段头部 object 名称错误：initial/T

**现象：** 文件名为 T，FoamFile.object 却为 p_rgh。

**建议：** 将 object 改为 T，随后运行 foamDictionary/求解器启动检查。

### 5. [HIGH] 旋转后激光位置与计算域坐标需核验

**现象：** t=0 激光中心位于旋转后域外：y=20.000 μm，域范围 [-300.000,0.000] μm. 且 V_incident 按通常传播方向解释时指向远离计算域的一侧。

**建议：** 确认 LaserBeamFoam 对 V_incident 的符号定义；用 transformPoints 后的实际网格坐标重写轨迹，并在 ParaView 中显示激光中心/射线进行验证。

### 6. [MEDIUM] 字典 object 元数据陈旧：constant/LaserProperties

**现象：** FoamFile.object=PhaseFieldProperties，与文件名 LaserProperties 不一致。

**建议：** 统一 object 名称，减少版本迁移和自动检查歧义。

### 7. [MEDIUM] 字典 object 元数据陈旧：constant/physicalProperties.metal

**现象：** FoamFile.object=physicalProperties.water，与文件名 physicalProperties.metal 不一致。

**建议：** 统一 object 名称，减少版本迁移和自动检查歧义。

### 8. [MEDIUM] 字典 object 元数据陈旧：constant/physicalProperties.gas

**现象：** FoamFile.object=physicalProperties.air，与文件名 physicalProperties.gas 不一致。

**建议：** 统一 object 名称，减少版本迁移和自动检查歧义。

### 9. [MEDIUM] 模拟时间只覆盖激光计划的一部分

**现象：** endTime=100.000 μs，而移动轨迹定义到 1000.000 μs；本次仅覆盖约 10.0%。

**建议：** 在报告/目录名中明确这是 100 μs 初始段；若目标是整条 1 mm 扫描，将 endTime 延长到至少 1000 μs。

### 10. [MEDIUM] 截断高度与名义层厚的定义需要区分

**现象：** 按 100–180 μm 整个截断区计算，固相体积分数为 0.370；但按 check.py 的 50 μm 目标层厚计算，表观堆积率为 0.592。

**建议：** 报告中同时给出截断区厚度、目标名义层厚、等效致密厚度及顶部高度分布，避免把 180 μm 截断面直接当作均匀粉层顶面。

### 11. [MEDIUM] 最终 PSD 与输入 PSD 有明显选择性偏差

**现象：** 输入模板覆盖约 32.5–77.5 μm，但最终颗粒最大直径为 67.5 μm，较大颗粒可能在截断时被优先删除。

**建议：** 同时保存插入前、沉降后和截断后的 PSD；不要只用输入分布代表最终粉末床。

### 12. [MEDIUM] DEM 插入阶段出现受限插入警告

**现象：** 日志中检测到 110 次 “Less insertions than requested”。这通常表示当前插入区域/重叠约束无法在该事件中达到计划数量。

**建议：** 结合实际累计插入数检查；必要时扩大 factory 区、降低每事件数量、增加 ntry_mc 或延长插入阶段。

### 13. [MEDIUM] DEM 使用了显著软化的接触刚度

**现象：** youngsModulus=5e7（cgs 压力单位），等效约 5 MPa；这应被视为数值加速参数，而非 M247 的真实弹性模量。

**建议：** 记录软化依据，并对 Young 模量和 DEM 时间步进行敏感性检查，确认最终堆积率与 PSD 不依赖该数值选择。

### 14. [MEDIUM] DEM 时间步安全检查被注释

**现象：** input.liggghts 中存在 check/timestep/gran 示例，但当前未启用。

**建议：** 在材料/接触参数确定后临时启用 check/timestep/gran，记录 Rayleigh/Hertz 时间步比例，再决定生产 timestep。

### 15. [MEDIUM] DEM 结果不会自动同步到 CFD 算例

**现象：** DEM_large/Allrun 中复制 location 到 constant 的命令被注释，且示例路径写成 /post/location。

**建议：** 显式执行 cp post/location ../constant/location，并在复制后运行本审查脚本；建议把该步骤写入可失败即停止的工作流。

### 16. [MEDIUM] DEM 启动脚本含用户机器绝对路径

**现象：** DEM_large/Allrun 将 LIGGGHTS 可执行文件写死为 /home/...。

**建议：** 改用环境变量、PATH 或脚本参数，例如 ${LIGGGHTS_BIN:-liggghts}。

### 17. [LOW] setFieldsDict 当前未被 Allrun 使用

**现象：** 主流程执行 setSolidFraction，而不是 setFields。保留的 setFieldsDict 容易被误认为有效配置。

**建议：** 删除、归档或在 README 中标注该文件为弃用配置。

### 18. [LOW] 初始字段包含网格中不存在的边界条目

**现象：** 额外条目：defaultFaces。

**建议：** 清理 defaultFaces 等遗留条目，使边界字典与 blockMesh 完全一致。

### 19. [LOW] 激光子划分数较低

**现象：** N_sub_divisions=1。在自由表面曲率大或粉末多次反射敏感时，角向/面积积分分辨率可能不足。

**建议：** 先做 N_sub_divisions 的网格独立性/能量吸收敏感性对比，再决定生产值。

## 10. 建议的算例归档清单

每次正式计算建议同时归档以下内容：

1. 本报告与 JSON；Git commit/hash；OpenFOAM、LaserBeamFoam、LIGGGHTS 版本和编译选项。
2. `checkMesh`、`setSolidFraction`、求解器完整日志，以及并行分解与重构日志。
3. 粉末床的最终 `location`、PSD、体积分数、顶部高度分布、截断前后颗粒数。
4. 激光轨迹在最终旋转坐标系中的可视化截图或采样点；明确传播向量符号约定。
5. 能量守恒、最大温度、熔池长/宽/深、熔化体积、气液界面质量守恒和 Courant 数历史。

---
本报告是静态配置审查，不能替代实际运行时的 `checkMesh`、日志收敛检查、质量/能量守恒检查和结果物理验证。
