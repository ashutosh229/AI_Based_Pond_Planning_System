from dataclasses import dataclass

MAX_PRACTICAL_DEPTH_M = 4.0
MIN_PRACTICAL_DEPTH_M = 0.5


@dataclass(frozen=True)
class PondSizingResult:
    usable_volume_m3: float
    recommended_depth_m: float
    is_feasible: bool
    notes: str


class PondSizer:
    @staticmethod
    def usable_volume_m3(design_storage_volume_m3: float, loss_factor: float) -> float:
        if not (0 <= loss_factor < 1):
            raise ValueError("loss_factor must be in [0, 1)")
        return design_storage_volume_m3 * (1 - loss_factor)

    @classmethod
    def recommend(cls, design_storage_volume_m3: float, available_surface_area_m2: float, loss_factor: float) -> PondSizingResult:
        if available_surface_area_m2 <= 0:
            raise ValueError("available_surface_area_m2 must be positive")
        usable_volume = cls.usable_volume_m3(design_storage_volume_m3, loss_factor)
        depth = usable_volume / available_surface_area_m2

        if depth > MAX_PRACTICAL_DEPTH_M:
            return PondSizingResult(round(usable_volume, 2), round(depth, 2), False,
                f"Required depth ({depth:.2f} m) exceeds practical limit ({MAX_PRACTICAL_DEPTH_M} m).")
        if depth < MIN_PRACTICAL_DEPTH_M:
            return PondSizingResult(round(usable_volume, 2), round(depth, 2), True,
                f"Required depth ({depth:.2f} m) is shallow — high evaporation loss risk.")
        return PondSizingResult(round(usable_volume, 2), round(depth, 2), True, "Within practical depth range.")
