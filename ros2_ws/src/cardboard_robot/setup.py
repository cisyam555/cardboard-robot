from glob import glob
from setuptools import setup

setup(
    name="cardboard_robot", version="0.1.0", packages=["cardboard_robot"],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/cardboard_robot"]),
        ("share/cardboard_robot", ["package.xml"]),
        ("share/cardboard_robot/launch", glob("launch/*.launch.py")),
    ],
    install_requires=["setuptools"], zip_safe=True,
    maintainer="cisyam555", maintainer_email="cisyam555@users.noreply.github.com",
    description="ROS2 learning robot with topics, services and parameterized launch", license="LicenseRef-Project",
    entry_points={"console_scripts": [
        "hardware_bridge = cardboard_robot.bridge:main",
        "behavior_controller = cardboard_robot.behavior:main",
    ]},
)
