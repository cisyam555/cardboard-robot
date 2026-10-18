# 用法：在项目根目录执行 source tools/ros2_env.bash
# 每个学习终端都 source 同一文件；只改变当前终端，不修改 ~/.bashrc。
if [[ -z "${BASH_VERSION:-}" ]]; then
    printf '%s\n' '请在 Bash 终端中 source 本文件。' >&2
    return 1
fi
cardboard_project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ ! -f "$cardboard_project_root/ros2_ws/install/setup.bash" ]]; then
    printf '%s\n' '还没有构建工作空间。请先按 README 执行 colcon build。' >&2
    unset cardboard_project_root
    return 1
fi
source /opt/ros/jazzy/setup.bash || return 1
source "$cardboard_project_root/ros2_ws/install/setup.bash" || return 1
unset ROS_LOCALHOST_ONLY ROS_STATIC_PEERS
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
# 学习终端使用同一通信域；需要与其他项目区分时可预设 CARDBOARD_ROS_DOMAIN_ID。
export ROS_DOMAIN_ID="${CARDBOARD_ROS_DOMAIN_ID:-74}"
printf 'ROS2 学习环境：仅本机通信，通信域 %s。\n' "$ROS_DOMAIN_ID"
unset cardboard_project_root
