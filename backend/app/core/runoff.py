from dataclasses import dataclass


@dataclass(frozen=True)
class RunoffResult:
    annual_runoff_volume_m3: float
    design_storage_volume_m3: float


class RunoffCalculator:
    @staticmethod
    def annual_runoff_volume_m3(catchment_area_m2: float, annual_rainfall_m: float, runoff_coefficient: float) -> float:
        if catchment_area_m2 <= 0:
            raise ValueError("catchment_area_m2 must be positive")
        if annual_rainfall_m < 0:
            raise ValueError("annual_rainfall_m cannot be negative")
        if not (0 < runoff_coefficient <= 1):
            raise ValueError("runoff_coefficient must be in (0, 1]")
        return runoff_coefficient * catchment_area_m2 * annual_rainfall_m

    @staticmethod
    def design_storage_volume_m3(annual_runoff_volume_m3: float, capture_fraction: float) -> float:
        if not (0 < capture_fraction <= 1):
            raise ValueError("capture_fraction must be in (0, 1]")
        return annual_runoff_volume_m3 * capture_fraction

    @classmethod
    def compute(cls, catchment_area_m2, annual_rainfall_m, runoff_coefficient, capture_fraction) -> RunoffResult:
        annual_volume = cls.annual_runoff_volume_m3(catchment_area_m2, annual_rainfall_m, runoff_coefficient)
        design_volume = cls.design_storage_volume_m3(annual_volume, capture_fraction)
        return RunoffResult(round(annual_volume, 2), round(design_volume, 2))

    @staticmethod
    def peak_flow_m3_per_s(runoff_coefficient: float, rainfall_intensity_mm_per_hr: float, catchment_area_hectares: float) -> float:
        return (runoff_coefficient * rainfall_intensity_mm_per_hr * catchment_area_hectares) / 360
