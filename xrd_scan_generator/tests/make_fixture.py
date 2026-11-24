"""Writes tests/fixtures/SAMPLE.xrdml: a small, invented XRDML 1.5 scan (quartz/calcite-like peaks on a background,
Poisson noise). It is not a measurement. Run: python tests/make_fixture.py"""
from pathlib import Path
import numpy as np

def pv(x, c, w, eta=0.45):
    d = (x - c) / w
    return eta / (1 + 4 * d * d) + (1 - eta) * np.exp(-4 * np.log(2) * d * d)

def build(path, sample_id="SAMPLE", name="SAMPLE", n=6500, tag="intensities", crlf=True):
    rng = np.random.default_rng(7)
    x = np.linspace(5.0, 70.0, n)
    bg = 260 - 1.6 * x + 40 * np.exp(-0.5 * ((x - 28) / 6) ** 2)
    peaks = [(20.86, 1500), (26.64, 7600), (29.41, 5200), (36.55, 600), (39.40, 900), (43.15, 700),
             (47.50, 1100), (48.50, 850), (50.14, 1300), (59.96, 450), (64.70, 380), (68.14, 520)]
    y = bg.copy()
    for c, h in peaks:
        y += h * pv(x, c, 0.09)
        th = np.radians(c / 2); d2 = 2 * np.degrees(np.arcsin(1.544426 / 1.540598 * np.sin(th))) - c
        y += 0.5 * h * pv(x, c + d2, 0.09)
    counts = rng.poisson(y)
    nl = "\r\n" if crlf else "\n"
    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<xrdMeasurements xmlns="http://www.xrdml.com/XRDMeasurement/1.5" status="Completed">
	<sample type="To be analyzed">
		<id>{sample_id}</id>
		<name>{name}</name>
		<preparedBy>test fixture</preparedBy>
	</sample>
	<xrdMeasurement measurementType="Scan" status="Completed">
		<usedWavelength intended="K-Alpha 1">
			<kAlpha1 unit="Angstrom">1.5405980</kAlpha1>
			<kAlpha2 unit="Angstrom">1.5444260</kAlpha2>
			<ratioKAlpha2KAlpha1>0.5000</ratioKAlpha2KAlpha1>
		</usedWavelength>
		<scan appendNumber="0" mode="Continuous" scanAxis="Gonio" status="Completed">
			<header>
				<startTimeStamp>2025-03-01T10:00:00+01:00</startTimeStamp>
				<endTimeStamp>2025-03-01T11:00:00+01:00</endTimeStamp>
			</header>
			<dataPoints>
				<positions axis="2Theta" unit="deg">
					<startPosition>{x[0]:.8f}</startPosition>
					<endPosition>{x[-1]:.8f}</endPosition>
				</positions>
				<positions axis="Omega" unit="deg">
					<startPosition>{x[0] / 2:.8f}</startPosition>
					<endPosition>{x[-1] / 2:.8f}</endPosition>
				</positions>
				<commonCountingTime unit="seconds">0.50</commonCountingTime>
				<{tag} unit="counts">{" ".join(map(str, counts))}</{tag}>
			</dataPoints>
		</scan>
	</xrdMeasurement>
</xrdMeasurements>
'''
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline=nl) as f:
        f.write(xml)
    return path

if __name__ == "__main__":
    print(build(Path(__file__).parent / "fixtures" / "SAMPLE.xrdml"))
