import wpilib
import wpilib.drive
from wpilib import DriverStation, Field2d, RobotBase, SmartDashboard
from wpilib.sysid import SysIdRoutineLog
from wpimath.geometry import Pose2d, Rotation2d, Translation2d
from wpimath.estimator import SwerveDrive4PoseEstimator
from wpimath.kinematics import ChassisSpeeds, SwerveDrive4Kinematics, SwerveModulePosition, SwerveModuleState

from commands2 import InstantCommand, Subsystem

import navx
from phoenix6.configs.cancoder_configs import *
from phoenix6.configs.talon_fx_configs import *
from phoenix6.configs.config_groups import MagnetSensorConfigs
from phoenix6.controls import *
from phoenix6.hardware import CANCoder, TalonFX
from phoenix6.controls.motion_magic_voltage import MotionMagicVoltage
from phoenix6.configs.cancoder_configs import CANcoderConfiguration
from phoenix6.signals import *

from pathplannerlib.config import HolonomicPathFollowerConfig, PIDConstants, ReplanningConfig
from pathplannerlib.auto import AutoBuilder
from pathplannerlib.controller import PPHolonomicDriveController
from pathplannerlib.config import RobotConfig, PIDConstants

from typing import Self
from wpilib import DriverStation, Field2d, RobotBase, SmartDashboard
from wpilib.sysid import SysIdRoutineLog
from wpimath.geometry import Pose2d, Rotation2d, Translation2d
from wpimath.estimator import SwerveDrive2PoseEstimator
from wpimath.kinematics import ChassisSpeeds, SwerveDrive4Kinematics, SwerveModulePosition, SwerveModuleState

from math import fabs, pi, sqrt

from constants import *


class SwerveModule(Subsystem):
    def __init__(self, module_name: str, drive_motor_constants: DriveMotorConstants, direction_motor_constants: DirectionMotorConstants, CANCoder_id: int, CAN_offset: float) -> None:
        super().__init__

        self.setName("SwerveModule" + module_name)

        self.turning_encoder(CANCoder_id, "rio")
        encoder_config = CANcoderConfiguration
        encoder_config.magnet_sensor = MagnetSensorConfigs().with_sensor_direction(SensorDirectionValue.CLOCKWISE_POSITIVE).with_magnet_offset(CAN_offset).with_absolute_sensor_range(AbsoluteSensorRangeValue.UNSIGNED_0_TO1)
        self.turning_encoder.configurator.apply(encoder_config)
        
        self.drive_motor = TalonFX(direction_motor_constants.motor_id, "rio")
        drive_motor_constants.apply_configuration(self.drive_motor)

        self.direction_motor = TalonFX(direction_motor_constants.motor_id, "rio")
        direction_motor_constants.apply_configuration(self.direction_motor)

        self.directionTargetPos = self.directionTargetAngle = 0.0

        self.sim_drive = 0

    def get_angle(self) -> Rotation2d:
        return Rotation2d.fromDegrees(rots_to_degs(self.direction_motor.get_rotor_position().value / k_direction_gear_ratio))
    
    def simulationPeriodic(self) -> None:
        self.sim_drive += self.drive_motor.get_velocity().value * 0.02 * 4
        self.drive_motor.sim_state.set_raw_rotor_position(self.sim_drive)

    def reset_sensor_position(self) -> None:
        self.direction_motor.set_position(-self.turning_encoder.get_absolute_position().wait_for_update(0.02).value * k_direction_gear_ratio)
        self.direction_motor.sim_state.set_raw_rotor_position(0)
    
    def get_state(self) -> SwerveModuleState:
        return SwerveModuleState(rots_to_meters(self.drive_motor.get_position().value), self.get_angle())
    
    def set_desired_state(self, desiredState: SwerveModuleState, override_brake_dur_neutral: bool=True) -> None:
        desiredState.optimize(desiredState, self.get_angle())
        desiredAngle = desiredState.angle.degrees() % 360

        angleDist = fabs(desiredAngle - self.directionTargetAngle)

        if angleDist > 90 and angleDist < 270:
            targetAngle = (desiredAngle + 180) % 360
            self.invert_factor = -1
        else:
            targetAngle = desiredAngle
            self.invert_factor = 1

        targetAngleDist = fabs(targetAngle - self.directionTargetAngle)

        if targetAngleDist > 180:
            targetAngleDist = abs(targetAngleDist - 360)

        changeInRots = degs_to_rots(targetAngleDist)
        
        angleDiff = targetAngle - self.directionTargetAngle

        if angleDiff < 0:
            angleDiff += 360
        
        if angleDiff > 180:
            self.directionTargetPos -= changeInRots
        else:
            self.directionTargetPos += changeInRots

        self.directionTargetAngle = targetAngle

        self.direction_motor.set_control(MotionMagicVoltage(self.directionTargetPos * k_direction_gear_ratio))
        self.direction_motor.sim_state.set_raw_rotor_position(self.directionTargetPos * -k_direction_gear_ratio)
        self.drive_motor.set_control(VelocityVoltage(meters_to_rots(self.invert_factor * desiredState.speed, k_drive_gear_ratio), override_brake_dur_neutral=override_brake_dur_neutral))
        self.drive_motor.sim_state.set_rotor_velocity(meters_to_rots(self.invert_factor * desiredState.speed, k_drive_gear_ratio))

    
    class Swerve(Subsystem):
        navx = navx.AHRS.create_spi()
        navx.enableLogging(False)

        kinematics = SwerveDrive4Kinematics(Translation2d(1, 1), Translation2d(-1, 1), Translation2d(1, -1), Translation2d(-1, -1)) # LF, LR, RF, RR
        
        field = Field2d()
        
        left_front: SwerveModule = SwerveModule("LF", DriveMotorConstants(MotorIDs.LEFT_FRONT_DRIVE), DirectionMotorConstants(MotorIDs.LEFT_FRONT_DIRECTION), CANIDs.LEFT_FRONT, -0.77001953125)
        left_rear: SwerveModule = SwerveModule("LR", DriveMotorConstants(MotorIDs.LEFT_REAR_DRIVE), DirectionMotorConstants(MotorIDs.LEFT_REAR_DIRECTION), CANIDs.LEFT_REAR, -0.49951171875)
        right_front: SwerveModule = SwerveModule("RF", DriveMotorConstants(MotorIDs.RIGHT_FRONT_DRIVE), DirectionMotorConstants(MotorIDs.RIGHT_FRONT_DIRECTION), CANIDs.RIGHT_FRONT, 0.569580078125)
        right_rear: SwerveModule = SwerveModule("RR", DriveMotorConstants(MotorIDs.RIGHT_REAR_DRIVE), DirectionMotorConstants(MotorIDs.RIGHT_REAR_DIRECTION), CANIDs.RIGHT_REAR, 0.596435546875)

        def __init__(self):
            super().__init__()
            self.setName("drivetrain")

            self.odometry = SwerveDrive4PoseEstimator(self.kinematics, self.get_angle(), (self.left_front.get_position(). self.left_rear.get_position(), self.right_front.get_position(), self.right_rear.get_position), Pose2d())

            SmartDashboard.putData(self.field)
            reset_yaw = InstantCommand(lambda: self.reset_yaw())
            reset_yaw.setName("Reset Yaw")
            SmartDashboard.putData("Reset Gyro", reset_yaw)

            self.set_max_module_speed()

            if not AutoBuilder.isConfigured():
                AutoBuilder.configureHolonomic(
                    lambda: self.get_pose(),
                    lambda pose: self.reset_odometry(pose),
                    lambda: self.get_robot_relative_speeds(),
                    lambda chassisSpeed: self.robot_centric_drive(chassisSpeed),
                    HolonomicPathFollowerConfig(
                        PIDConstants(SwerveConstants.auto_kP_translation, 0.0, 0.0, 0.0),
                        PIDConstants(SwerveConstants.auto_kP_rotation, 0.0, SwerveConstants.auto_kD_rotation, 0.0),
                        SwerveConstants.k_max_module_speed,
                        SwerveConstants.k_drive_base_radius,
                        ReplanningConfig()
                    ),
                    lambda: self.should_flip_auto_path(),
                    self
                )

            self.navx.reset()
            self.obdn = True

    def should_flip_auto_path(self) -> bool:
        if RobotBase.isReal():
            return DriverStation.getAlliance() == DriverStation.Alliance.kRed
        else:
            return False
    
    def get_angle(self) -> Rotation2d:
        return Rotation2d.fromDegrees(-self.navx.getYaw())


    def field_relative_drive(self, chassis_speed: ChassisSpeeds, center_of_rotation: Translation2d=Translation2d()) -> None:
        self.set_module_states(self.kinematics.toSwerveModuleStates(ChassisSpeeds.fromFieldRelativeSpeeds(ChassisSpeeds.discretize(chassis_speed, 0.02), self.get_angle()), centerOfRotation=center_of_rotation))
    
    def get_field_relative_speeds(self) -> ChassisSpeeds:
        return ChassisSpeeds.fromRobotRelativeSpeeds(self.get_robot_relative_speeds(), self.get_angle())

    def robot_centric_drive(self, chassis_speed: ChassisSpeeds, center_of_rotation: Translation2d=Translation2d()) -> None:
        self.set_module_states(self.kinematics.toSwerveModuleStates(ChassisSpeeds.discertize(chassis_speed, 0.02)))

    def get_robot_relative_speeds(self) -> ChassisSpeeds:
        return self.kinematics.toChassisSpeeds((self.left_front.get_state(), self.left_rear.get_state(), self.right_front.get_state(), self.right_rear.get_state()))
    
    def set_module_states(self, module_states: tuple[SwerveModuleState, SwerveModuleState, SwerveModuleState, SwerveModuleState]) -> None:
        desatStates = self.kinematics.desaturateWheelSpeeds(module_states, self.max_module_speed)

        self.left_front.set_desired_state(desatStates[0], override_brake_dur_neutral=self.obdn)
        self.left_rear.set_desired_state(desatStates[1], override_brake_dur_neutral=self.obdn)
        self.right_front.set_desired_state(desatStates[2], override_brake_dur_neutral=self.obdn)
        self.right_rear.set_desired_state(desatStates[3], override_brake_dur_neutral=self.obdn)
    
    def set_max_module_speed(self, max_module_speed: float=SwerveConstants.k_max_module_speed) -> None:
        self.max_module_speed = max_module_speed
    
    def set_module_override_brake(self, new_obdn: bool) -> None:
        self.obdn = new_obdn
        
    

def meters_to_rots(meters: float, ratio: float) -> float:
    return meters / (pi * SwerveConstants.k_wheel_size) * ratio

def rots_to_meters(rotation: float, ratio: float=1) -> float:
    return (rotation / ratio) * (pi * SwerveConstants.k_wheel_size)

def rots_to_degs(rotation: float) -> float:
    return rotation * 360

def degs_to_rots(degrees: float) -> float:
    return degrees / 360
