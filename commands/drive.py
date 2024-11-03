from commands2 import Command
from constants import *
from enum import Enum
from subsystems.swerve import Swerve
from wpilib import XboxController
from wpilib import SmartDashboard
from wpilib.kinematics import ChassisSpeeds
from math import copysign

class DriveModes(Enum):
    FIELD_RELATIVE = 0
    ROBOT_CENTRIC = 1

class DriveByController(Command):
    def __init__(self, swerve: Swerve, controller: XboxController) -> None:
        super().__init__()

        self.swerve = swerve
        self.addRequirements(self.swerve)

        self.controller = controller
        self.mode = DriveModes.FIELD_RELATIVE

    def execute(self) -> None:
        translation_y = (copysign(1, -self.controller.getLeftX()) * abs(self.controller.getLeftX()) ** (3/2)) * SwerveConstants.k_max_module_speed
        translation_x = (copysign(1, -self.controller.getLeftY()) * abs(self.controller.getLeftY()) ** (3/2)) * SwerveConstants.k_max_module_speed

        rotation = (copysign(1, -self.controller.getRightX()) * abs(self.controller.getRightX()) ** (3/2)) * SwerveConstants.k_max_rot_rate

        slowdown_mult = 1
        if self.controller.getRightBumper():
            slowdown_mult+=1
        
        if self.mode == DriveModes.FIELD_RELATIVE:
            self.swerve.field_relative_drive(ChassisSpeeds(translation_x / slowdown_mult, translation_y / slowdown_mult, rotation / slowdown_mult))

        if self.controller.getYButtonPressed() and False:
            if self.mode == DriveMOdes.FIELD_RELATIVE:
                self.mode = DriveModes.ROBOT_CENTRIC
            else:
                self.mode = DriveModes.FIELD_RELATIVE
        
    def end(self, interrupted: bool) -> None:
        return super().end(interrupted)
    
    def isFinished(self) -> None:
        return False
