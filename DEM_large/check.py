#!/usr/bin/env python3

from pathlib import Path
from math import pi
import sys


# =========================
# 用户参数
# =========================

LOCATION_FILE = Path("post/location")

# 几何尺寸，单位 μm
DOMAIN_X_UM = 300.0
DOMAIN_Y_UM = 1200.0

PLATE_TOP_UM = 100.0
TRIM_TOP_UM = 180.0

# 目标名义粉层
TARGET_LAYER_UM = 50.0
TARGET_PACKING_FRACTION = 0.58

# 当前粒径模板范围
EXPECTED_RADIUS_MIN_UM = 16.25
EXPECTED_RADIUS_MAX_UM = 38.75

# M247 密度
POWDER_DENSITY_KG_M3 = 8540.0

# 判断几何越界时允许的数值误差
TOLERANCE_UM = 1.0


def percentile(values, fraction):
    """简单线性插值分位数。fraction 取 0~1。"""
    values = sorted(values)

    if not values:
        raise ValueError("空数据无法计算分位数")

    if len(values) == 1:
        return values[0]

    position = fraction * (len(values) - 1)
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    weight = position - lower

    return values[lower] * (1.0 - weight) + values[upper] * weight


def find_column(columns, possible_names):
    for name in possible_names:
        if name in columns:
            return columns.index(name)

    raise ValueError(
        f"找不到列 {possible_names}，文件实际列名为：{columns}"
    )


def read_location(path):
    """
    返回：
        timestep
        [(x, y, z, radius), ...]
    坐标单位保持文件原单位，当前应为 m。
    """

    if not path.exists():
        raise FileNotFoundError(f"找不到文件：{path}")

    lines = path.read_text(errors="ignore").splitlines()

    has_dump_header = any(
        line.startswith("ITEM: TIMESTEP") for line in lines
    )

    # -------------------------
    # LIGGGHTS dump 格式
    # -------------------------
    if has_dump_header:
        frame_starts = [
            i for i, line in enumerate(lines)
            if line.startswith("ITEM: TIMESTEP")
        ]

        # 只读取最后一个时间帧
        start = frame_starts[-1]
        end = len(lines)

        timestep = int(float(lines[start + 1].strip()))

        number_index = None
        atoms_index = None

        for i in range(start, end):
            if lines[i].startswith("ITEM: NUMBER OF ATOMS"):
                number_index = i

            if lines[i].startswith("ITEM: ATOMS"):
                atoms_index = i
                break

        if number_index is None:
            raise ValueError("没有找到 ITEM: NUMBER OF ATOMS")

        if atoms_index is None:
            raise ValueError("没有找到 ITEM: ATOMS")

        number_of_atoms = int(float(lines[number_index + 1].strip()))

        columns = lines[atoms_index].split()[2:]

        ix = find_column(columns, ["v_x1", "x1", "x"])
        iy = find_column(columns, ["v_y1", "y1", "y"])
        iz = find_column(columns, ["v_z1", "z1", "z"])
        ir = find_column(columns, ["v_rad1", "rad1", "radius", "r"])

        particles = []

        first_data_line = atoms_index + 1
        last_data_line = first_data_line + number_of_atoms

        for line in lines[first_data_line:last_data_line]:
            values = line.split()

            if len(values) < len(columns):
                continue

            particles.append(
                (
                    float(values[ix]),
                    float(values[iy]),
                    float(values[iz]),
                    float(values[ir]),
                )
            )

        if len(particles) != number_of_atoms:
            print(
                "警告：文件声明的颗粒数为 "
                f"{number_of_atoms}，实际读取到 {len(particles)}"
            )

        return timestep, particles

    # -------------------------
    # 纯四列格式
    # -------------------------
    particles = []

    for line_number, line in enumerate(lines, start=1):
        line = line.strip()

        if not line or line.startswith("#"):
            continue

        values = line.split()

        if len(values) != 4:
            continue

        try:
            x, y, z, radius = map(float, values)
        except ValueError:
            print(f"跳过无法解析的第 {line_number} 行：{line}")
            continue

        particles.append((x, y, z, radius))

    return None, particles


def pass_fail(condition):
    return "通过" if condition else "注意"


def main():
    try:
        timestep, particles = read_location(LOCATION_FILE)
    except Exception as error:
        print(f"读取失败：{error}")
        sys.exit(1)

    if not particles:
        print("location 文件中没有读取到颗粒数据。")
        sys.exit(1)

    # location 当前应当是 m
    xs_um = [particle[0] * 1.0e6 for particle in particles]
    ys_um = [particle[1] * 1.0e6 for particle in particles]
    zs_um = [particle[2] * 1.0e6 for particle in particles]
    rs_um = [particle[3] * 1.0e6 for particle in particles]
    ds_um = [2.0 * radius for radius in rs_um]

    x_min_extent = min(x - r for x, r in zip(xs_um, rs_um))
    x_max_extent = max(x + r for x, r in zip(xs_um, rs_um))

    y_min_extent = min(y - r for y, r in zip(ys_um, rs_um))
    y_max_extent = max(y + r for y, r in zip(ys_um, rs_um))

    z_min_extent = min(z - r for z, r in zip(zs_um, rs_um))
    z_max_extent = max(z + r for z, r in zip(zs_um, rs_um))

    # 颗粒总体积，使用 m
    particle_volume_m3 = sum(
        4.0 / 3.0 * pi * radius_m**3
        for _, _, _, radius_m in particles
    )

    particle_mass_kg = (
        particle_volume_m3 * POWDER_DENSITY_KG_M3
    )

    bed_area_m2 = (
        DOMAIN_X_UM * 1.0e-6
        * DOMAIN_Y_UM * 1.0e-6
    )

    # 将全部粉末压成完全致密层时对应的厚度
    equivalent_dense_thickness_um = (
        particle_volume_m3 / bed_area_m2 * 1.0e6
    )

    # 若实际堆积率为 0.58，对应的名义粉层厚度
    estimated_layer_thickness_um = (
        equivalent_dense_thickness_um
        / TARGET_PACKING_FRACTION
    )

    # 若强行认为粉层厚度是 50 μm，对应的表观堆积率
    apparent_packing_fraction = (
        equivalent_dense_thickness_um
        / TARGET_LAYER_UM
    )

    print("=" * 64)
    print("LIGGGHTS 最终粉末床检查")
    print("=" * 64)

    print(f"文件：{LOCATION_FILE}")

    if timestep is not None:
        print(f"最后时间步：{timestep}")

    print(f"颗粒数量：{len(particles)}")

    print()
    print("1. 颗粒中心坐标范围，单位 μm")
    print(f"X center: {min(xs_um):.3f} ～ {max(xs_um):.3f}")
    print(f"Y center: {min(ys_um):.3f} ～ {max(ys_um):.3f}")
    print(f"Z center: {min(zs_um):.3f} ～ {max(zs_um):.3f}")

    print()
    print("2. 颗粒外轮廓范围，单位 μm")
    print(f"X extent: {x_min_extent:.3f} ～ {x_max_extent:.3f}")
    print(f"Y extent: {y_min_extent:.3f} ～ {y_max_extent:.3f}")
    print(f"Z extent: {z_min_extent:.3f} ～ {z_max_extent:.3f}")

    print()
    print("3. 粒径统计，单位 μm")
    print(f"最小半径：{min(rs_um):.3f}")
    print(f"最大半径：{max(rs_um):.3f}")
    print(f"最小直径：{min(ds_um):.3f}")
    print(f"D10：{percentile(ds_um, 0.10):.3f}")
    print(f"D50：{percentile(ds_um, 0.50):.3f}")
    print(f"D90：{percentile(ds_um, 0.90):.3f}")
    print(f"最大直径：{max(ds_um):.3f}")

    print()
    print("4. 粉末量估算")
    print(f"颗粒总体积：{particle_volume_m3:.6e} m³")
    print(f"颗粒总质量：{particle_mass_kg * 1.0e6:.6f} mg")
    print(
        "等效全致密层厚度："
        f"{equivalent_dense_thickness_um:.3f} μm"
    )
    print(
        f"假设堆积率为 {TARGET_PACKING_FRACTION:.2f}，"
        "估算名义粉层厚度："
        f"{estimated_layer_thickness_um:.3f} μm"
    )
    print(
        f"若按目标层厚 {TARGET_LAYER_UM:.1f} μm 计算，"
        "表观堆积率："
        f"{apparent_packing_fraction:.4f}"
    )

    print()
    print("5. 自动检查")

    x_ok = (
        x_min_extent >= -TOLERANCE_UM
        and x_max_extent <= DOMAIN_X_UM + TOLERANCE_UM
    )

    y_ok = (
        y_min_extent >= -TOLERANCE_UM
        and y_max_extent <= DOMAIN_Y_UM + TOLERANCE_UM
    )

    plate_ok = (
        z_min_extent >= PLATE_TOP_UM - TOLERANCE_UM
    )

    trim_ok = (
        z_max_extent <= TRIM_TOP_UM + TOLERANCE_UM
    )

    radius_ok = (
        min(rs_um) >= EXPECTED_RADIUS_MIN_UM - 0.1
        and max(rs_um) <= EXPECTED_RADIUS_MAX_UM + 0.1
    )

    print(
        f"[{pass_fail(x_ok)}] X 方向颗粒是否位于 "
        f"0～{DOMAIN_X_UM:.0f} μm"
    )

    print(
        f"[{pass_fail(y_ok)}] Y 方向颗粒是否位于 "
        f"0～{DOMAIN_Y_UM:.0f} μm"
    )

    print(
        f"[{pass_fail(plate_ok)}] 最低颗粒是否位于 "
        f"{PLATE_TOP_UM:.0f} μm 基板顶面以上"
    )

    print(
        f"[{pass_fail(trim_ok)}] 最高颗粒是否低于 "
        f"{TRIM_TOP_UM:.0f} μm 裁剪高度"
    )

    print(
        f"[{pass_fail(radius_ok)}] 半径是否位于 "
        f"{EXPECTED_RADIUS_MIN_UM:.2f}～"
        f"{EXPECTED_RADIUS_MAX_UM:.2f} μm"
    )

    target_dense_thickness_um = (
        TARGET_LAYER_UM * TARGET_PACKING_FRACTION
    )

    print()
    print("6. 目标粉末量参考")
    print(
        f"{TARGET_LAYER_UM:.1f} μm 名义层厚、"
        f"堆积率 {TARGET_PACKING_FRACTION:.2f} 时，"
        "目标等效致密层厚度应约为："
        f"{target_dense_thickness_um:.3f} μm"
    )

    ratio = (
        equivalent_dense_thickness_um
        / target_dense_thickness_um
    )

    print(f"当前粉末量 / 目标粉末量：{ratio:.3f}")

    if ratio > 1.20:
        print("判断：当前粉末总量明显偏多。")
    elif ratio < 0.80:
        print("判断：当前粉末总量明显偏少。")
    else:
        print("判断：当前粉末总量接近目标范围。")

    print("=" * 64)


if __name__ == "__main__":
    main()