"""
RoadWatch AI - Seed Script
Generates 20 realistic road damage inspection reports around Bhubaneswar, India,
with varied severity, damage types, status, and generated demo road defect images.
"""

import os
import random
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont

from db import init_db, insert_report

# Ensure uploads directory exists
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def create_demo_road_image(filename: str, damage_type: str, severity: str, index: int) -> str:
    """Generates a realistic synthetic road surface image with visual defects and annotation."""
    img_width, img_height = 800, 600
    # Road asphalt base colour
    base_color = (random.randint(45, 60), random.randint(45, 60), random.randint(48, 62))
    img = Image.new("RGB", (img_width, img_height), color=base_color)
    draw = ImageDraw.Draw(img)

    # Add road surface texture / noise
    for _ in range(800):
        nx = random.randint(0, img_width - 1)
        ny = random.randint(0, img_height - 1)
        shade = random.randint(30, 80)
        draw.point((nx, ny), fill=(shade, shade, shade))

    # Draw lane marking (yellow or white dashed line)
    lane_color = (230, 190, 40) if index % 2 == 0 else (220, 220, 220)
    for y in range(0, img_height, 70):
        draw.rectangle([img_width // 2 - 8, y, img_width // 2 + 8, y + 40], fill=lane_color)

    # Draw simulated damage
    if damage_type == "pothole":
        # Draw 1 or more pothole craters
        num_holes = 2 if severity == "High" else 1
        for h in range(num_holes):
            cx = 250 + h * 220 + random.randint(-30, 30)
            cy = 300 + random.randint(-40, 40)
            rx = random.randint(55, 90)
            ry = random.randint(35, 60)
            # Outer broken rim
            draw.ellipse([cx - rx - 8, cy - ry - 8, cx + rx + 8, cy + ry + 8], fill=(30, 30, 30))
            # Deep hole depression
            draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=(15, 15, 15))
            # Inner shadow/depth
            draw.ellipse([cx - rx + 15, cy - ry + 10, cx + rx - 10, cy + ry - 8], fill=(5, 5, 5))

    elif damage_type == "alligator crack":
        # Interconnected polygonal mesh cracks
        mesh_points = []
        for gx in range(150, 650, 45):
            for gy in range(200, 500, 45):
                mesh_points.append((gx + random.randint(-15, 15), gy + random.randint(-15, 15)))
        for pt1 in mesh_points:
            for pt2 in random.sample(mesh_points, min(3, len(mesh_points))):
                dist = ((pt1[0] - pt2[0]) ** 2 + (pt1[1] - pt2[1]) ** 2) ** 0.5
                if dist < 65:
                    draw.line([pt1, pt2], fill=(20, 20, 20), width=random.randint(2, 4))

    else:  # "crack"
        # Longitudinal or transverse crack line with jagged branches
        start_x = random.randint(180, 260)
        start_y = random.randint(120, 180)
        curr = (start_x, start_y)
        for _ in range(8):
            next_x = curr[0] + random.randint(40, 70)
            next_y = curr[1] + random.randint(25, 55)
            draw.line([curr, (next_x, next_y)], fill=(18, 18, 18), width=random.randint(3, 5))
            # Small branch
            if random.random() > 0.4:
                branch_end = (next_x + random.randint(-20, 30), next_y + random.randint(20, 40))
                draw.line([(next_x, next_y), branch_end], fill=(25, 25, 25), width=2)
            curr = (next_x, next_y)

    # Top overlay header banner
    draw.rectangle([0, 0, img_width, 45], fill=(0, 0, 0, 180))
    # Severity badge color
    sev_color = (220, 53, 69) if severity == "High" else ((253, 126, 20) if severity == "Medium" else (40, 167, 69))
    draw.rectangle([10, 8, 110, 36], fill=sev_color)

    # Annotations
    draw.text((18, 14), f"{severity.upper()}", fill=(255, 255, 255))
    draw.text((125, 14), f"RoadWatch Inspection Demo #{index:02d} | {damage_type.title()}", fill=(240, 240, 240))

    dest_path = os.path.join(UPLOAD_DIR, filename)
    img.save(dest_path, format="JPEG", quality=85)
    return dest_path


DEMO_REPORTS = [
    {
        "location_name": "KIIT Square, Patia",
        "latitude": 20.3540,
        "longitude": 85.8175,
        "damage_type": "pothole",
        "pothole_count": 2,
        "damage_percent": 52.0,
        "severity": "High",
        "confidence": 0.94,
        "status": "Reported",
        "summary": "Multiple deep potholes near the pedestrian crossing causing severe vehicle deceleration.",
        "recommended_action": "Emergency cold asphalt patching followed by heavy roller compaction.",
        "days_ago": 1,
    },
    {
        "location_name": "Infocity Avenue, DLF Cybercity",
        "latitude": 20.3582,
        "longitude": 85.8142,
        "damage_type": "crack",
        "pothole_count": 0,
        "damage_percent": 12.0,
        "severity": "Low",
        "confidence": 0.89,
        "status": "Fixed",
        "summary": "Minor longitudinal hairline shrinkage crack along the shoulder edge.",
        "recommended_action": "Sealed with hot-pour bituminous polymer sealant.",
        "days_ago": 8,
    },
    {
        "location_name": "Jayadev Vihar Overbridge Approach",
        "latitude": 20.3015,
        "longitude": 85.8236,
        "damage_type": "pothole",
        "pothole_count": 3,
        "damage_percent": 58.0,
        "severity": "High",
        "confidence": 0.96,
        "status": "In Progress",
        "summary": "Cluster of 3 sharp-edged potholes on main flyover ascent creating hazard for two-wheelers.",
        "recommended_action": "Milling of affected asphalt course and hot mix asphalt overlay.",
        "days_ago": 2,
    },
    {
        "location_name": "Master Canteen Station Circle",
        "latitude": 20.2662,
        "longitude": 85.8431,
        "damage_type": "alligator crack",
        "pothole_count": 0,
        "damage_percent": 48.0,
        "severity": "High",
        "confidence": 0.92,
        "status": "Assigned",
        "summary": "Extensive crocodile fatigue cracking indicating base course fatigue under heavy bus traffic.",
        "recommended_action": "Subgrade excavation, granular sub-base reinforcement, and full-depth reconstruction.",
        "days_ago": 3,
    },
    {
        "location_name": "Saheed Nagar Janpath Boulevard",
        "latitude": 20.2885,
        "longitude": 85.8420,
        "damage_type": "pothole",
        "pothole_count": 1,
        "damage_percent": 24.0,
        "severity": "Medium",
        "confidence": 0.91,
        "status": "Reported",
        "summary": "Isolated mid-lane pothole around 8 cm deep along the commercial shopping corridor.",
        "recommended_action": "Clean cavity debris, apply tack coat, and compact with warm mix asphalt.",
        "days_ago": 1,
    },
    {
        "location_name": "Vani Vihar Junction (NH-16)",
        "latitude": 20.3021,
        "longitude": 85.8504,
        "damage_type": "pothole",
        "pothole_count": 4,
        "damage_percent": 65.0,
        "severity": "High",
        "confidence": 0.97,
        "status": "Assigned",
        "summary": "Severe surface cratering spanning 4 consecutive potholes near the highway exit ramp.",
        "recommended_action": "Urgent temporary cold-mix patch and lane closure for full pavement rehabilitation.",
        "days_ago": 4,
    },
    {
        "location_name": "Rasulgarh Industrial Square",
        "latitude": 20.2982,
        "longitude": 85.8647,
        "damage_type": "alligator crack",
        "pothole_count": 0,
        "damage_percent": 44.0,
        "severity": "High",
        "confidence": 0.93,
        "status": "In Progress",
        "summary": "Interlocking fatigue fracture network across left commercial traffic lane.",
        "recommended_action": "Deep asphalt recycling and micro-surfacing protective seal.",
        "days_ago": 3,
    },
    {
        "location_name": "Khandagiri Caves Foothill Road",
        "latitude": 20.2598,
        "longitude": 85.7865,
        "damage_type": "crack",
        "pothole_count": 0,
        "damage_percent": 14.0,
        "severity": "Low",
        "confidence": 0.88,
        "status": "Fixed",
        "summary": "Transverse thermal crack extending 1.5 meters from kerb edge.",
        "recommended_action": "High-pressure air cleaning and elastomeric sealant injection completed.",
        "days_ago": 10,
    },
    {
        "location_name": "Baramunda ISBT Terminal Gate",
        "latitude": 20.2764,
        "longitude": 85.7981,
        "damage_type": "pothole",
        "pothole_count": 2,
        "damage_percent": 34.0,
        "severity": "Medium",
        "confidence": 0.90,
        "status": "Reported",
        "summary": "Dual depressions formed near bus terminal deceleration lane.",
        "recommended_action": "Square-cut edges, tack coat application, and dense bituminous macadam filling.",
        "days_ago": 1,
    },
    {
        "location_name": "Nayapalli CRP Square Crossway",
        "latitude": 20.2934,
        "longitude": 85.8115,
        "damage_type": "crack",
        "pothole_count": 0,
        "damage_percent": 28.0,
        "severity": "Medium",
        "confidence": 0.87,
        "status": "In Progress",
        "summary": "Multiple longitudinal reflective cracks along pavement expansion joints.",
        "recommended_action": "Crack routing and rubberized asphalt filler sealing.",
        "days_ago": 5,
    },
    {
        "location_name": "Acharya Vihar Science Park Road",
        "latitude": 20.3040,
        "longitude": 85.8340,
        "damage_type": "pothole",
        "pothole_count": 1,
        "damage_percent": 22.0,
        "severity": "Medium",
        "confidence": 0.92,
        "status": "Fixed",
        "summary": "Round pothole near stormwater grate repaired with premix asphalt.",
        "recommended_action": "Repaired and levelled with vibrating plate compactor.",
        "days_ago": 7,
    },
    {
        "location_name": "Chandrasekharpur Damana Square",
        "latitude": 20.3341,
        "longitude": 85.8190,
        "damage_type": "alligator crack",
        "pothole_count": 0,
        "damage_percent": 55.0,
        "severity": "High",
        "confidence": 0.95,
        "status": "Reported",
        "summary": "Wide alligator pattern surface failure with loose aggregate displacement.",
        "recommended_action": "Full-depth excavation, sub-base stabilization, and 50mm asphalt concrete resurfacing.",
        "days_ago": 0,
    },
    {
        "location_name": "Sailashree Vihar Phase 2 Sector",
        "latitude": 20.3421,
        "longitude": 85.8110,
        "damage_type": "crack",
        "pothole_count": 0,
        "damage_percent": 11.0,
        "severity": "Low",
        "confidence": 0.86,
        "status": "Reported",
        "summary": "Superficial drying shrinkage cracks on residential access lane.",
        "recommended_action": "Slurry seal surfacing during upcoming annual neighborhood maintenance.",
        "days_ago": 2,
    },
    {
        "location_name": "Kalpana Square Court Road",
        "latitude": 20.2520,
        "longitude": 85.8415,
        "damage_type": "pothole",
        "pothole_count": 3,
        "damage_percent": 60.0,
        "severity": "High",
        "confidence": 0.96,
        "status": "In Progress",
        "summary": "Deep contiguous potholes causing water ponding and traffic bottleneck.",
        "recommended_action": "Dewatering, crushed stone ballast filling, and dense asphalt topping.",
        "days_ago": 3,
    },
    {
        "location_name": "Old Town Lingaraj Temple North Gate",
        "latitude": 20.2395,
        "longitude": 85.8340,
        "damage_type": "crack",
        "pothole_count": 0,
        "damage_percent": 15.0,
        "severity": "Low",
        "confidence": 0.89,
        "status": "Fixed",
        "summary": "Minor pavement surface seam widening alongside stone kerbing.",
        "recommended_action": "Flexible polyurethane joint sealing successfully completed.",
        "days_ago": 12,
    },
    {
        "location_name": "Pokhariput Ananda Bazar Crossing",
        "latitude": 20.2450,
        "longitude": 85.8035,
        "damage_type": "pothole",
        "pothole_count": 1,
        "damage_percent": 26.0,
        "severity": "Medium",
        "confidence": 0.90,
        "status": "Assigned",
        "summary": "Single sharp crater on inner curve hazardous during monsoon rains.",
        "recommended_action": "Excavate damaged periphery and refill with high-performance cold patch.",
        "days_ago": 2,
    },
    {
        "location_name": "Biju Patnaik Airport Outer Ring",
        "latitude": 20.2545,
        "longitude": 85.8180,
        "damage_type": "crack",
        "pothole_count": 0,
        "damage_percent": 9.0,
        "severity": "Low",
        "confidence": 0.93,
        "status": "Fixed",
        "summary": "Early-stage hairline longitudinal crack along utility trench cut.",
        "recommended_action": "Preventative emulsified bitumen crack bandaging applied.",
        "days_ago": 14,
    },
    {
        "location_name": "Mancheswar Industrial Estate Sector-B",
        "latitude": 20.3210,
        "longitude": 85.8610,
        "damage_type": "alligator crack",
        "pothole_count": 0,
        "damage_percent": 62.0,
        "severity": "High",
        "confidence": 0.95,
        "status": "Reported",
        "summary": "Severe alligator structural failure caused by repeated overloaded heavy transport trucks.",
        "recommended_action": "Complete pavement milling and high-modulus asphalt concrete reconstruction.",
        "days_ago": 1,
    },
    {
        "location_name": "Unit-4 MLA Colony Access Street",
        "latitude": 20.2715,
        "longitude": 85.8290,
        "damage_type": "crack",
        "pothole_count": 0,
        "damage_percent": 13.0,
        "severity": "Low",
        "confidence": 0.87,
        "status": "Reported",
        "summary": "Surface block cracking along asphalt edge adjoining pedestrian footpath.",
        "recommended_action": "Low-viscosity asphalt emulsion seal coat.",
        "days_ago": 2,
    },
    {
        "location_name": "Dumduma Housing Board Main Rd",
        "latitude": 20.2490,
        "longitude": 85.7790,
        "damage_type": "pothole",
        "pothole_count": 2,
        "damage_percent": 35.0,
        "severity": "Medium",
        "confidence": 0.91,
        "status": "Assigned",
        "summary": "Two medium potholes forming along rainwater runoff channel.",
        "recommended_action": "Saw-cut edges, tack coat, and hot asphalt roller compaction.",
        "days_ago": 3,
    },
]


def seed_database(reset: bool = False):
    """Initializes the database and seeds 20 realistic demo reports."""
    if reset:
        db_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports.db")
        if os.path.exists(db_file):
            try:
                os.remove(db_file)
            except Exception:
                pass

    print("Initializing RoadWatch AI database...")
    init_db()


    base_time = datetime.now()
    created_count = 0

    print(f"Generating 20 demo inspection reports around Bhubaneswar, India...")
    for idx, report_data in enumerate(DEMO_REPORTS, start=1):
        filename = f"seed_report_{idx:02d}.jpg"
        image_path = create_demo_road_image(
            filename=filename,
            damage_type=report_data["damage_type"],
            severity=report_data["severity"],
            index=idx,
        )

        timestamp = (base_time - timedelta(days=report_data["days_ago"], hours=idx * 2)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        rep_id = insert_report(
            image_path=image_path,
            latitude=report_data["latitude"],
            longitude=report_data["longitude"],
            damage_type=report_data["damage_type"],
            pothole_count=report_data["pothole_count"],
            damage_percent=report_data["damage_percent"],
            severity=report_data["severity"],
            confidence=report_data["confidence"],
            summary=report_data["summary"],
            recommended_action=report_data["recommended_action"],
            user_description=f"Citizen report near {report_data['location_name']}.",
            status=report_data["status"],
            created_at=timestamp,
        )
        created_count += 1
        print(f"  [+] Report #{rep_id:02d}: {report_data['location_name']} - {report_data['severity']} ({report_data['status']})")

    print(f"\nSuccessfully seeded {created_count} reports into SQLite database!")


if __name__ == "__main__":
    seed_database(reset=True)

