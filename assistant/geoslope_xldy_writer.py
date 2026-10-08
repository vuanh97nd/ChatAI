"""
Generate GeoSlope SLOPE/W .gsz stability analysis files for Vietnamese road segments.

XML structure derived from KM30+560-CDM.gsz, KM30+560 TRƯỚC XỬ LÝ.gsz,
Km 133+180 - thay dat.gsz, Km 134+300-DTD+CT.gsz (GeoStudio 2025, version 11.08).

Engineering basis: TCVN 9362:2012; Bishop simplified method; Fs ≥ 1.2 (thi công), ≥ 1.4 (khai thác).
"""
from __future__ import annotations

import io
import json
import math
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Default soil parameter sets by treatment type
# ---------------------------------------------------------------------------

_DEFAULT_SOILS = {
    "fill": {
        "name": "Vat lieu dap", "model": "MohrCoulomb",
        "gamma": 18.0, "c_prime": 15.0, "phi_prime": 20.0,
        "color": "RGB=(255,255,128)",
    },
    "soft_upper": {
        "name": "Lop dat yeu 1", "model": "UndrainedPhiZero",
        "gamma": 16.0, "cohesion": 8.0,
        "color": "RGB=(255,128,0)",
    },
    "soft_lower": {
        "name": "Lop dat yeu 2", "model": "UndrainedPhiZero",
        "gamma": 16.5, "cohesion": 12.0,
        "color": "RGB=(255,200,100)",
    },
    "bearing": {
        "name": "Nen cung", "model": "MohrCoulomb",
        "gamma": 18.5, "c_prime": 25.0, "phi_prime": 22.0,
        "color": "RGB=(128,255,191)",
    },
    "cdm": {
        "name": "CDM", "model": "UndrainedPhiZero",
        "gamma": 16.8, "cohesion": 85.0,
        "color": "RGB=(191,128,255)",
    },
    "sand_replacement": {
        "name": "Cat thay the", "model": "MohrCoulomb",
        "gamma": 18.4, "c_prime": 5.0, "phi_prime": 28.0,
        "color": "RGB=(255,255,200)",
    },
    "high_strength": {
        "name": "BT / CT", "model": "HighStrength",
        "gamma": 24.5,
        "color": "RGB=(128,191,255)",
    },
    "pvd_consolidated": {
        "name": "Dat sau xu ly", "model": "UndrainedPhiZero",
        "gamma": 17.0, "cohesion": 25.0,
        "color": "RGB=(200,255,200)",
    },
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt(v: float, decimals: int = 6) -> str:
    """Format a float removing unnecessary trailing zeros."""
    s = f"{v:.{decimals}f}".rstrip("0").rstrip(".")
    return s if s and s != "-" else "0"


def _material_xml(mat_id: int, info: dict) -> str:
    """Return <Material> XML block."""
    model = info.get("model", "MohrCoulomb")
    gamma = info.get("gamma", 18.0)
    color = info.get("color", "RGB=(200,200,200)")
    name  = info.get("name", f"Mat{mat_id}")

    ss_lines = [
        "        <JointEffectiveCohesion Missing=\"true\" />",
        "        <IntactRockParam Missing=\"true\" />",
        "        <GeologicalStrengthIndex Missing=\"true\" />",
        "        <DisturbanceFactor Missing=\"true\" />",
        "        <MaxConfiningStress Missing=\"true\" />",
        f"        <UnitWeight>{_fmt(gamma)}</UnitWeight>",
    ]
    if model == "UndrainedPhiZero":
        cohesion = info.get("cohesion", 10.0)
        ss_lines.append(f"        <Cohesion>{_fmt(cohesion)}</Cohesion>")
    elif model == "MohrCoulomb":
        c_prime   = info.get("c_prime", 0.0)
        phi_prime = info.get("phi_prime", 20.0)
        if c_prime:
            ss_lines.append(f"        <CohesionPrime>{_fmt(c_prime)}</CohesionPrime>")
        ss_lines.append(f"        <PhiPrime>{_fmt(phi_prime)}</PhiPrime>")
    # HighStrength has no strength parameters in the template files
    ss_lines += [
        "        <YoungsPrimeModulus Missing=\"true\" />",
        "        <EffectivePoissonsRatio Missing=\"true\" />",
        "        <EPrimeModulusXPrime Missing=\"true\" />",
        "        <EffectivePoissonsRatioXPrime Missing=\"true\" />",
        "        <EPrimeModulusYPrime Missing=\"true\" />",
        "        <EffectivePoissonsRatioYPrime Missing=\"true\" />",
        "        <ShearModulusXYPrime Missing=\"true\" />",
        "        <OCRatio Missing=\"true\" />",
    ]
    ss_body = "\n".join(ss_lines)
    return f"""    <Material>
      <ID>{mat_id}</ID>
      <Color>{color}</Color>
      <Name>{name}</Name>
      <SlopeModel>{model}</SlopeModel>
      <StressStrain>
{ss_body}
      </StressStrain>
    </Material>"""


# ---------------------------------------------------------------------------
# Cross-section geometry builder
# ---------------------------------------------------------------------------

class _CrossSection:
    """
    Simple half-embankment cross-section (symmetrical, left half only for stability).

    Coordinate system: X increases to the right, Y is elevation.
    Origin (0, 0) = centreline at original ground surface.

    Zones modelled:
      Region 1 = embankment fill (above ground, right side)
      Region 2 = treatment zone / soft soil upper (ground to -(htk/2))
      Region 3 = soft soil lower ((htk/2) to -htk)
      Region 4 = bearing stratum (below -htk to -bottom)
    """

    SLOPE_H  = 1.5   # horizontal / vertical (1:1.5)
    HALF_W   = 6.0   # road half-width (m)
    SHOULDER = 1.0   # shoulder strip
    MARGIN   = 40.0  # model width to the right of centreline
    BOTTOM   = 4.0   # depth below bottom of soft soil layer

    def __init__(self, hdy: float, htk: float, treatment: str,
                 excav: float = 0.0, pile_len: float = 0.0):
        self.hdy = max(hdy, 0.5)
        self.htk = max(htk, 1.0)
        self.treatment = (treatment or "").lower()
        self.excav = max(excav, 0.0)   # excavation depth for DAO_THAY
        self.pile_len = pile_len       # pile (CDM) depth into ground

        # Key elevations
        self.y_road = self.hdy          # road surface
        self.y_gnd  = 0.0              # original ground surface
        self.y_soft_mid = -(self.htk / 2)
        self.y_soft_bot = -self.htk
        self.y_model_bot = -(self.htk + self.BOTTOM)

        # Width at toe of embankment
        self.x_toe = self.HALF_W + self.SHOULDER + self.hdy * self.SLOPE_H
        self.x_right = max(self.MARGIN, self.x_toe + 20.0)

    # ----- Points -----------------------------------------------------------

    def _build_points(self) -> list[tuple[float, float]]:
        """Return list of (x, y) for all boundary points, 1-indexed."""
        h = self.hdy
        hw = self.HALF_W
        sh = self.SHOULDER
        sl = self.SLOPE_H
        xe = self.x_toe
        xR = self.x_right

        pts: list[tuple[float, float]] = []

        def P(x, y):
            pts.append((_fmt(x, 6), _fmt(y, 6)))

        # Road surface corners
        P(0,        h)           # 1 centreline top
        P(hw,       h)           # 2 road edge
        P(hw + sh,  h)           # 3 shoulder edge
        P(xe,       0.0)         # 4 toe at ground
        P(xR,       0.0)         # 5 far right ground
        P(xR,       self.y_soft_mid)   # 6
        P(xR,       self.y_soft_bot)   # 7
        P(xR,       self.y_model_bot)  # 8 bottom right
        P(0,        self.y_model_bot)  # 9 bottom left
        P(0,        self.y_soft_bot)   # 10
        P(0,        self.y_soft_mid)   # 11
        P(0,        0.0)              # 12 centreline ground

        if self.treatment in ("cdm",) and self.pile_len > 0:
            # CDM column bounding box (centred on centreline, width hw)
            cdm_top = 0.0
            cdm_bot = min(-self.pile_len, self.y_soft_bot)
            P(hw,  cdm_top)    # 13
            P(hw,  cdm_bot)    # 14
            P(0,   cdm_bot)    # 15

        return pts

    def _build_regions(self, n_pts: int, has_cdm: bool) -> list[list[int]]:
        """
        Return list of region point-index lists (1-based).
        Region order:
          1 = fill (embankment)
          2 = soft upper / treatment zone
          3 = soft lower
          4 = bearing stratum
        Optionally 5 = CDM columns
        """
        regions = []

        if has_cdm:
            # fill: 1-2-3-4-12-13-1
            regions.append([1, 2, 3, 4, 12, 13])
            # CDM zone: 13-14-15-12-13
            regions.append([13, 14, 15, 12])
            # soft upper minus CDM: 4-5-6-11-12-13-14-15-10 (rough approx)
            regions.append([4, 5, 6, 11, 12, 13, 14, 15, 10])
            # soft lower
            regions.append([10, 11, 6, 7])
            # bearing
            regions.append([10, 7, 8, 9])
        else:
            # fill: pts 1,2,3,4,12
            regions.append([1, 2, 3, 4, 12])
            # soft upper: 4,5,6,11,12
            regions.append([4, 5, 6, 11, 12])
            # soft lower: 11,6,7,10
            regions.append([11, 6, 7, 10])
            # bearing: 10,7,8,9
            regions.append([10, 7, 8, 9])

        return regions

    # ----- Public XML builders ---------------------------------------------

    def build_geometry_xml(self) -> tuple[str, list[list[int]]]:
        """Return (geometry XML string, list of region point-index lists)."""
        pts = self._build_points()
        has_cdm = self.treatment == "cdm" and self.pile_len > 0
        regions = self._build_regions(len(pts), has_cdm)

        pt_lines = []
        for i, (x, y) in enumerate(pts, 1):
            pt_lines.append(f'        <Point ID="{i}" X="{x}" Y="{y}" />')

        # Lines: boundary edges connecting consecutive points in each region
        seen: set[tuple[int, int]] = set()
        line_pairs: list[tuple[int, int]] = []

        def add_edge(a, b):
            key = (min(a, b), max(a, b))
            if key not in seen:
                seen.add(key)
                line_pairs.append((a, b))

        for reg in regions:
            for k in range(len(reg)):
                add_edge(reg[k], reg[(k + 1) % len(reg)])

        line_lines = []
        for i, (a, b) in enumerate(line_pairs, 1):
            line_lines.append(
                f"        <Line>\n"
                f"          <ID>{i}</ID>\n"
                f"          <PointID1>{a}</PointID1>\n"
                f"          <PointID2>{b}</PointID2>\n"
                f"        </Line>"
            )

        region_lines = []
        for i, reg in enumerate(regions, 1):
            ids = ",".join(str(x) for x in reg)
            region_lines.append(
                f"        <Region>\n"
                f"          <ID>{i}</ID>\n"
                f"          <PointIDs>{ids}</PointIDs>\n"
                f"        </Region>"
            )

        geom = (
            f"      <Name>2D Geometry</Name>\n"
            f"      <Points Len=\"{len(pts)}\">\n"
            + "\n".join(pt_lines) + "\n"
            f"      </Points>\n"
            f"      <Lines Len=\"{len(line_pairs)}\">\n"
            + "\n".join(line_lines) + "\n"
            f"      </Lines>\n"
            f"      <Regions Len=\"{len(regions)}\">\n"
            + "\n".join(region_lines) + "\n"
            f"      </Regions>\n"
        )
        return geom, regions

    def build_slip_surface_xml(self) -> str:
        """Return <SlipSurface> entry for GridAndRadius method."""
        # Entry: from centreline at road surface to right side
        entry_xl = _fmt(-self.HALF_W * 0.5)
        entry_xr = _fmt(self.HALF_W)
        entry_y  = _fmt(self.hdy * 0.9)
        exit_xl  = _fmt(self.x_toe * 0.8)
        exit_xr  = _fmt(self.x_right * 0.9)
        exit_y   = _fmt(self.y_gnd - 0.5)
        lim_xl   = "0"
        lim_yl   = _fmt(self.hdy)
        lim_xr   = _fmt(self.x_right)
        lim_yr   = _fmt(self.y_model_bot)

        return f"""        <SlipSurface>
          <Grid NumXInc="4" NumYInc="4" Angle1="" Angle2="" NumAngleDiv="2" />
          <Radius NumInc="20" />
          <EntryExit>
            <LeftSideLeftPt X="{entry_xl}" Y="{entry_y}" />
            <LeftSideRightPt X="{entry_xr}" Y="{entry_y}" />
            <LeftInc>20</LeftInc>
            <RightSideLeftPt X="{exit_xl}" Y="{exit_y}" />
            <RightSideRightPt X="{exit_xr}" Y="{exit_y}" />
            <RightInc>20</RightInc>
          </EntryExit>
          <EntryExit3D>
            <Entry>
              <Points Len="3">
                <Point Z="" />
                <Point Z="" />
                <Point Z="" />
              </Points>
              <NumIncrements Len="2">
                <Inc>4</Inc>
                <Inc>4</Inc>
              </NumIncrements>
            </Entry>
            <Exit>
              <Points Len="3">
                <Point Z="" />
                <Point Z="" />
                <Point Z="" />
              </Points>
              <NumIncrements Len="2">
                <Inc>4</Inc>
                <Inc>4</Inc>
              </NumIncrements>
            </Exit>
            <RadiusInfo>
              <AspectRatios Len="1">
                <AspectRatio>1</AspectRatio>
              </AspectRatios>
              <NExponents Len="1">
                <NExponent>2</NExponent>
              </NExponents>
            </RadiusInfo>
          </EntryExit3D>
          <Block>
            <LeftGrid NumXInc="4" NumYInc="4" Angle1="" Angle2="" NumAngleDiv="2" ArrowCorner="Undefined" />
            <RightGrid NumXInc="4" NumYInc="4" Angle1="" Angle2="" NumAngleDiv="2" ArrowCorner="Undefined" />
          </Block>
          <Limit XLeft="{lim_xl}" YLeft="{lim_yl}" XRight="{lim_xr}" YRight="{lim_yr}" />
          <MinimumVolume>1</MinimumVolume>
        </SlipSurface>"""


# ---------------------------------------------------------------------------
# Material list builder by treatment type
# ---------------------------------------------------------------------------

def _build_materials(treatment: str, soil_params: Optional[list]) -> list[dict]:
    """
    Return ordered list of material dicts matching the region order:
      [fill, treatment/soft_upper, soft_lower, bearing, (optional treatment zone)]

    Region→Material mapping (1-based, same as Context.GeometryUsesMaterials):
      Regions-1 = fill
      Regions-2 = soft upper / CDM zone
      Regions-3 = soft lower
      Regions-4 = bearing
    """
    t = (treatment or "").lower()

    # Allow caller to override individual layers via soil_params
    sp = {}
    if soil_params:
        for p in soil_params:
            role = p.get("role", "")
            if role:
                sp[role] = p

    def _override(base: dict, role: str) -> dict:
        if role not in sp:
            return base
        o = sp[role]
        out = dict(base)
        for k in ("name", "gamma", "cohesion", "c_prime", "phi_prime"):
            if k in o:
                out[k] = o[k]
        return out

    fill   = _override(dict(_DEFAULT_SOILS["fill"]),         "fill")
    s_up   = _override(dict(_DEFAULT_SOILS["soft_upper"]),   "soft_upper")
    s_lo   = _override(dict(_DEFAULT_SOILS["soft_lower"]),   "soft_lower")
    bear   = _override(dict(_DEFAULT_SOILS["bearing"]),      "bearing")

    if t == "cdm":
        cdm = _override(dict(_DEFAULT_SOILS["cdm"]), "cdm")
        # Regions: 1=fill, 2=CDM zone, 3=soft_upper, 4=soft_lower, 5=bearing
        mats = [fill, cdm, s_up, s_lo, bear]
        region_mat = [1, 2, 3, 4, 5]
    elif t in ("pvd", "sd", "pvd/sd", "bac_tham", "gieng_cat"):
        pvd = _override(dict(_DEFAULT_SOILS["pvd_consolidated"]), "pvd_consolidated")
        pvd["name"] = "Dat xu ly PVD"
        mats = [fill, pvd, s_lo, bear]
        region_mat = [1, 2, 3, 4]
    elif t in ("dao_thay", "thay_dat", "sand_replacement"):
        sand = _override(dict(_DEFAULT_SOILS["sand_replacement"]), "sand_replacement")
        mats = [fill, sand, s_lo, bear]
        region_mat = [1, 2, 3, 4]
    elif t in ("dtdct", "dao_thay_coc_tre", "coc_tre"):
        sand = _override(dict(_DEFAULT_SOILS["sand_replacement"]), "sand_replacement")
        ct   = _override(dict(_DEFAULT_SOILS["high_strength"]), "high_strength")
        ct["name"] = "Coc tre"
        mats = [fill, sand, ct, s_lo, bear]
        region_mat = [1, 2, 3, 4, 5]
    else:
        # Default: no treatment (before treatment analysis)
        mats = [fill, s_up, s_lo, bear]
        region_mat = [1, 2, 3, 4]

    # Assign IDs
    for i, m in enumerate(mats, 1):
        m["id"] = i

    return mats, region_mat


# ---------------------------------------------------------------------------
# Top-level XML builder
# ---------------------------------------------------------------------------

def _build_xml(project_name: str, analysis_name: str, method: str,
               cs: _CrossSection, mats: list[dict], region_mat: list[int]) -> str:
    now = datetime.now()
    date_str = now.strftime("%m/%d/%Y")
    time_str = now.strftime("%I:%M:%S %p")

    geom_body, _regions = cs.build_geometry_xml()
    slip_xml = cs.build_slip_surface_xml()

    mat_xmls = "\n".join(_material_xml(m["id"], m) for m in mats)
    mat_len = len(mats)

    # GeometryUsesMaterials: one entry per region
    gum_lines = []
    for i, mid in enumerate(region_mat, 1):
        gum_lines.append(f'        <GeometryUsesMaterial ID="Regions-{i}" Entry="{mid}" />')
    gum_xml = "\n".join(gum_lines)
    gum_len = len(region_mat)

    # DataPoints for stability entry: top of embankment road surface
    dp_xl = _fmt(-cs.HALF_W)
    dp_xr = _fmt(cs.HALF_W)
    dp_y  = _fmt(cs.hdy + 0.5)

    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<GSIData Version="11.08" AppVersion="25.1.1.182">
  <FileInfo FileVersion="11.08" AppVersion="25.1.1.182" RevNumber="1" Date="{date_str}" Time="{time_str}" />
  <Analyses Len="1">
    <Analysis>
      <ID>1</ID>
      <Name>{analysis_name}</Name>
      <Kind>SLOPE/W</Kind>
      <Method>{method}</Method>
      <GeometryId>1</GeometryId>
      <TimeIncrements>
        <Duration Missing="true" />
        <TimeSteps Len="1">
          <TimeStep Save="true" />
        </TimeSteps>
      </TimeIncrements>
      <IterationControls Len="1">
        <IterationControl>
          <Key>SlopeStability</Key>
          <Entry MaxIterations="100" MaxReviewIterations="10" />
        </IterationControl>
      </IterationControls>
      <UnderRelaxationCriteria Len="1">
        <UnderRelaxationCriterion>
          <Key>SlipFOS</Key>
          <Entry NumIterations="50" />
        </UnderRelaxationCriterion>
      </UnderRelaxationCriteria>
      <ComputedPhysics SlopeStability="true" />
    </Analysis>
  </Analyses>
  <BCs Len="8">
    <BC ID="1" Name="Fixed X" Color="RGB=(192,0,0)" XDisp="DispDisplacementX(Variability=Constant,Value=0)" YDisp="ForceDispUndefined()" />
    <BC ID="2" Name="Fixed Y" Color="RGB=(192,0,0)" XDisp="ForceDispUndefined()" YDisp="DispDisplacementY(Variability=Constant,Value=0)" />
    <BC ID="3" Name="Fixed X/Y" Color="RGB=(192,0,0)" XDisp="DispDisplacementX(Variability=Constant,Value=0)" YDisp="DispDisplacementY(Variability=Constant,Value=0)" />
    <BC ID="4" Name="Zero Pressure" Color="RGB=(192,0,0)" Hydraulic="HydPressureHead(Variability=Constant,Value=0)" />
    <BC ID="5" Name="Drainage" Color="RGB=(128,0,128)" Hydraulic="HydTotalFlux(Variability=Constant,Value=0,Review=true)" />
    <BC ID="6" Name="Unit Concentration" Color="RGB=(192,0,0)" Contaminant="ContamConcentrationVsTime(Variability=Constant,Value=1e-06)" />
    <BC ID="7" Name="Zero Rotation" Color="RGB=(192,0,0)" Rotation="ZeroRotation()" />
    <BC ID="8" Name="Atmospheric - Zero" Color="RGB=(192,0,0)" Air="AirPressure(Variability=Constant,Value=0)" />
  </BCs>
  <Contexts Len="1">
    <Context>
      <AnalysisID>1</AnalysisID>
      <GeometryUsesMaterials Len="{gum_len}">
{gum_xml}
      </GeometryUsesMaterials>
      <IsDefined>true</IsDefined>
    </Context>
  </Contexts>
  <Coordinates>
    <EngCoords HorzScale="200" XPageLeft="-10" YPageBottom="-{_fmt(cs.htk + cs.BOTTOM + 5)}" XPageRight="{_fmt(cs.x_right + 10)}" YPageTop="{_fmt(cs.hdy + 10)}" XPageOrg="10" YPageOrg="{_fmt(cs.htk + cs.BOTTOM + 5)}" MaxSnapDist="20" UnitSystem="Metric" LockScales="false" VertScale="200" />
    <PageCoords Units="in" PageWidth="34.44881889763779" PageHeight="26.24671916010498" PageXOrg="3.280905511811024" PageYOrg="7.0265748031496615" />
  </Coordinates>
  <Geometries Len="1">
    <Geometry>
{geom_body}    </Geometry>
  </Geometries>
  <Materials Len="{mat_len}">
{mat_xmls}
  </Materials>
  <PageLayout>
    <Units>mm</Units>
    <Margins>150</Margins>
    <Zoom>1</Zoom>
    <BasePt X="0" Y="0" />
    <GridSpacing>10</GridSpacing>
    <PageWidth>2970</PageWidth>
    <PageHeight>2100</PageHeight>
  </PageLayout>
  <StabilityItems Len="1">
    <StabilityItem>
      <AnalysisID>1</AnalysisID>
      <Entry>
        <DataPoints Len="2">
          <DataPoint Number="1" X="{dp_xl}" Y="{dp_y}" />
          <DataPoint Number="2" X="{dp_xr}" Y="{dp_y}" />
        </DataPoints>
{slip_xml}
        <LambdaSettings>
          <LambdaValues Len="11">
            <LambdaValues_>-1</LambdaValues_>
            <LambdaValues_>-0.8</LambdaValues_>
            <LambdaValues_>-0.6</LambdaValues_>
            <LambdaValues_>-0.4</LambdaValues_>
            <LambdaValues_>-0.2</LambdaValues_>
            <LambdaValues_ />
            <LambdaValues_>0.2</LambdaValues_>
            <LambdaValues_>0.4</LambdaValues_>
            <LambdaValues_>0.6</LambdaValues_>
            <LambdaValues_>0.8</LambdaValues_>
            <LambdaValues_>1</LambdaValues_>
          </LambdaValues>
        </LambdaSettings>
      </Entry>
    </StabilityItem>
  </StabilityItems>
  <WaterItems Len="1">
    <WaterItem>
      <AnalysisID>1</AnalysisID>
      <Entry>
        <UnitWaterWeight>9.807</UnitWaterWeight>
        <WaterBulkMod>2.08333333e+06</WaterBulkMod>
      </Entry>
    </WaterItem>
  </WaterItems>
</GSIData>"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def write_geoslope_gsz(
    path: str,
    segment: dict,
    soil_params: Optional[list] = None,
    method: str = "Bishop",
) -> dict:
    """
    Generate a GeoSlope SLOPE/W .gsz stability analysis file for a road segment.

    Parameters
    ----------
    path : str
        Output file path (must end with .gsz).
    segment : dict
        Road segment dict (from road_segment.py Segment). Keys used:
          sta_from, sta_to  – stationing labels (str/float)
          hdy               – embankment height (m)
          htk               – soft soil depth (m)
          treatment         – treatment code string
          pile_length       – CDM/pile length (m, optional)
          pile_spacing      – spacing (m, optional)
          excavation_depth  – excavation depth for DAO_THAY (m, optional)
    soil_params : list of dict, optional
        Override soil properties. Each dict:
          role (str): one of fill/soft_upper/soft_lower/bearing/cdm/pvd_consolidated/sand_replacement
          gamma, cohesion, c_prime, phi_prime, name (all optional)
    method : str
        Analysis method: Bishop (default), Morgenstern-Price, Spencer, Janbu, Ordinary.

    Returns
    -------
    dict
        {'output_path': str, 'analysis_type': str, 'slip_surfaces': int,
         'materials': int, 'regions': int}
    """
    valid_methods = {"Bishop", "Morgenstern-Price", "Spencer", "Janbu", "Ordinary"}
    if method not in valid_methods:
        raise ValueError(f"method phải là một trong: {', '.join(sorted(valid_methods))}")

    hdy  = float(segment.get("hdy") or 1.5)
    htk  = float(segment.get("htk") or 5.0)
    treat = str(segment.get("treatment") or "").strip()
    pile_len = float(segment.get("pile_length") or 0.0)
    excav    = float(segment.get("excavation_depth") or 0.0)

    sta_from = segment.get("sta_from", "")
    sta_to   = segment.get("sta_to", "")
    sta_label = f"Km{sta_from}-{sta_to}" if sta_from else "segment"

    treat_label = treat or "No Treatment"
    analysis_name = f"Slope Stability - {sta_label} - {treat_label}"
    if len(analysis_name) > 100:
        analysis_name = analysis_name[:100]

    cs = _CrossSection(hdy, htk, treat, excav=excav, pile_len=pile_len)
    mats, region_mat = _build_materials(treat, soil_params)
    xml_content = _build_xml(
        project_name=sta_label,
        analysis_name=analysis_name,
        method=method,
        cs=cs,
        mats=mats,
        region_mat=region_mat,
    )

    # Derive XML filename from output path
    out = Path(path)
    xml_name = out.stem + ".xml"

    # Pack into ZIP as .gsz
    out.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(xml_name, xml_content.encode("utf-8"))

    out.write_bytes(buf.getvalue())

    # Estimate slip surfaces: GridAndRadius = (NumXInc+1)*(NumYInc+1)*NumInc
    slip_surfaces = 5 * 5 * 20  # 4+1, 4+1, 20

    return {
        "output_path": str(out.resolve()),
        "analysis_type": method,
        "slip_surfaces": slip_surfaces,
        "materials": len(mats),
        "regions": len(region_mat),
    }


def write_geoslope_gsz_batch(
    output_dir: str,
    segments: list[dict],
    soil_params: Optional[list] = None,
    method: str = "Bishop",
    project_name: str = "",
) -> dict:
    """
    Generate one .gsz file per segment and return a summary.

    Parameters
    ----------
    output_dir : str
        Directory to write .gsz files into.
    segments : list of dict
        Road segment dicts (see write_geoslope_gsz).
    soil_params : list of dict, optional
    method : str
    project_name : str

    Returns
    -------
    dict  {'files': [{'path', 'sta', 'treatment'}...], 'count': int}
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for i, seg in enumerate(segments):
        sta_from = seg.get("sta_from", f"seg{i+1:03d}")
        treat = str(seg.get("treatment") or "NT")
        safe_sta = str(sta_from).replace("+", "_").replace(" ", "")
        safe_tr  = treat.replace("/", "_").replace(" ", "")[:20]
        fname = f"{safe_sta}_{safe_tr}.gsz"
        fpath = str(out_dir / fname)
        try:
            r = write_geoslope_gsz(fpath, seg, soil_params=soil_params, method=method)
            results.append({"path": r["output_path"], "sta": sta_from, "treatment": treat})
        except Exception as exc:
            results.append({"path": fpath, "sta": sta_from, "treatment": treat, "error": str(exc)})

    return {"files": results, "count": len(results), "output_dir": str(out_dir.resolve())}
