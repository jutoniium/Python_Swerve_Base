from commands.drive import DriveByController
from commands2.button import JoystickButton
from constants import *
from phoenix6.controls import DutyCycleOut
from subystems.swerve import Swerve
from wpilib import SendableChooser, SmartDashboard, Timer, XboxController
from wpimath.geometry import Pose2d, Rotation2d


class RobotContainer:

    def __init__(self):
        self.swerve: Swerve = Swerve()
        self.swerve.initialize()
        
        self.driverController = XboxController(ExternalConstants.DRIVERCONTROLLER)
        self.swerve.setDefaultCommand(DriveByController(self.swerve, self.driverController))

    def updateMatchTime(self) -> None:
        SmartDashboard.putNumber("Time", Timer.getMatchTime())
