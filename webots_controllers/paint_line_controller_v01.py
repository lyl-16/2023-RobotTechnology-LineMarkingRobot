"""paint_line_controller_v01 controller."""

# You may need to import some classes of the controller module. Ex:
#  from controller import Robot, Motor, DistanceSensor
from controller import *
import enum
import math


# 定义方向枚举
class Direction(enum.Enum):
    LEFT = 1
    RIGHT = 2


# 定义画圆的类型
class CircleType(enum.Enum):
    CIRCLE = 1
    SEMI = 2
    QUARTER = 3


# 定义MyRobot来对画线机器人进行进一步封装
class MyRobot:
    # 定义画线机器人的常量值
    GO_SPEED = 0.6  # 向前运动的速度 m/s
    ADJUST_SPEED = 0.01  # 偏移路线时回正的速度 m/s
    TURN_SPEED = 0.05  # m/s
    CIRCLE_SPEED = 0.15  # m/s
    SWITCH = 10.274509
    WIDTH = 0.325
    ADJUST_ANGLE = 0.05  # 需要路线修正的偏移角阈值

    # 定义画的线的相关常量值
    FLAG_RADIUS = 0.95  # 角旗区域圆弧的半径

    # 定义一些函数中要用到的中间量
    lastStepTime = -1.0
    nowTime = 0.0
    startPos = None
    footballPos = None
    footballNPos = None
    totalDistance = 0.0
    startAngle = -100.0
    rectangleStep = 1
    footballFieldStep = 0
    leftSpeed = GO_SPEED
    rightSpeed = GO_SPEED

    # 记录某个操作是否完成的标记量
    goFinished = False
    turnFinished = False
    rectangleFinished = False
    circleFinished = False
    footballFieldFinished = False

    def __init__(self):
        # 获取机器人api
        self.robot = Robot()
        # 获取基本模拟时间步
        self.timestep = int(self.robot.getBasicTimeStep())
        # 初始化相机
        self.camera = self.robot.getDevice('camera')
        self.camera.enable(self.timestep)
        # 初始化惯性测量单元
        self.imu = self.robot.getDevice('imu')
        self.imu.enable(self.timestep)
        # 初始化GPS
        self.gps = self.robot.getDevice('gps')
        self.gps.enable(self.timestep)
        # 获取两轮电机
        self.left_wheel = self.robot.getDevice('left wheel')
        self.right_wheel = self.robot.getDevice('right wheel')
        # 初始化画笔的
        self.pen = self.robot.getDevice('pen')
        self.pen.write(False)
        # 初始化两个轮子的状态
        self.left_wheel.setPosition(float('inf'))
        self.right_wheel.setPosition(float('inf'))
        self.setSpeed(0, 0)

    # 为两轮设置速度函数，SWITCH为速度与电机转速的转化比例
    def setSpeed(self, vl, vr):
        self.left_wheel.setVelocity(vl * self.SWITCH)
        self.right_wheel.setVelocity(vr * self.SWITCH)

    # 累加机器人走过的距离
    def addLineDistance(self):
        if self.lastStepTime < 0:
            self.lastStepTime = self.robot.getTime()
            return
        self.nowTime = self.robot.getTime()
        addDistance = self.gps.getSpeed() * (self.nowTime - self.lastStepTime)
        self.totalDistance += addDistance
        self.lastStepTime = self.nowTime

    # def goStraightOriginal(self, distance):
    #     if self.goFinished:
    #         return
    #     if self.totalDistance < distance:
    #         self.setSpeed(self.GO_SPEED, self.GO_SPEED)
    #         self.addLineDistance()
    #     else:
    #         self.setSpeed(0, 0)
    #         self.lastStepTime = -1.0
    #         self.totalDistance = 0.0
    #         self.goFinished = True

    # 机器人直线移动一定距离
    def goStraight(self, distance):
        if self.goFinished:
            return
        if self.startPos is None:
            # 初始化机器人的位置
            self.startPos = [self.gps.getValues()[0], self.gps.getValues()[2]]
            return
        nowPos = [self.gps.getValues()[0], self.gps.getValues()[2]]

        # 计算机器人走过的距离
        self.totalDistance = pow(pow(nowPos[0] - self.startPos[0], 2) + pow(nowPos[1] - self.startPos[1], 2), 0.5)
        # 如果走过的距离没达到设定的长度，继续向前走; 否则让机器人停下来
        if self.totalDistance < distance:
            # 对行走方向进行修正
            # 初始化开始的角度
            if self.startAngle == -100.0:
                self.startAngle = self.imu.getRollPitchYaw()[2]
            nowAngle = self.imu.getRollPitchYaw()[2]
            # 计算偏移的角度，若数值超过设定的阈值则进行两轮速度差的微调
            biasAngle = nowAngle - self.startAngle
            # 假如此时角度刚好转够3.14rad则会发生数值从-3.14突变到3.14(或从3.14突变到-3.14)的情况因此要进行特殊处理
            if self.startAngle * nowAngle < 0 and abs(nowAngle) > 1.5:
                if nowAngle < 0:
                    nowAngle = 2 * math.pi - abs(nowAngle)
                    biasAngle = self.startAngle - nowAngle
                else:
                    nowAngle = -(2 * math.pi - nowAngle)
                    biasAngle = self.startAngle - nowAngle
            if abs(biasAngle) >= self.ADJUST_ANGLE:
                # 向右偏移
                if biasAngle < 0:
                    self.leftSpeed -= self.ADJUST_SPEED
                    self.rightSpeed += self.ADJUST_SPEED
                else:
                    self.leftSpeed += self.ADJUST_SPEED
                    self.rightSpeed -= self.ADJUST_SPEED
            self.setSpeed(self.leftSpeed, self.rightSpeed)
        else:
            self.setSpeed(0, 0)
            self.totalDistance = 0.0
            self.startPos = None
            self.startAngle = -100.0
            self.goFinished = True
            self.leftSpeed = self.GO_SPEED
            self.rightSpeed = self.GO_SPEED

    # 机器人向左或向右转向某个角度
    def turn(self, direction, angle):
        # 转向角度不合理则直接退出
        if angle < 0 or angle > math.pi:
            print("not reasonable")
            return
        if self.turnFinished:
            return
        # 初始化开始的角度
        if self.startAngle == -100.0:
            self.startAngle = self.imu.getRollPitchYaw()[2]
        nowAngle = self.imu.getRollPitchYaw()[2]
        # 模拟器有一个bug，就是会以初始状态的角度作为正负的临界值
        # 假如此时角度刚好转够3.14rad则会发生数值从-3.14突变到3.14(或从3.14突变到-3.14)的情况因此要进行特殊处理(1.57也可能突变)
        if self.startAngle * nowAngle < 0 and 1.5 < abs(self.startAngle) < 3.2:
            # if abs(nowAngle) > 1.4:
            #     if nowAngle < 0:
            #         nowAngle = math.pi - abs(nowAngle)
            #     else:
            #         nowAngle = -(math.pi - nowAngle)
            # if abs(nowAngle) > 3.0:
            if nowAngle < 0:
                nowAngle = 2 * math.pi - abs(nowAngle)
            else:
                nowAngle = -(2 * math.pi - nowAngle)
        # 计算已转过的角度，若未达到设定的转向角则继续转，否则停下
        if abs(nowAngle - self.startAngle) < angle:
            if direction == Direction.LEFT:
                self.setSpeed(-self.TURN_SPEED, self.TURN_SPEED)
            else:
                self.setSpeed(self.TURN_SPEED, -self.TURN_SPEED)
        else:
            self.setSpeed(0, 0)
            self.startAngle = -100.0
            self.turnFinished = True

    # def circleAnyAngle(self, radius, angle):
    #     # TODO: 解决画任意角度的圆弧问题
    #     if angle < 0 or angle > 2 * math.pi:
    #         print("not reasonable")
    #         return
    #     if self.circleFinished:
    #         return
    #     distance = radius * angle
    #     if self.totalDistance < distance:
    #         vl = self.CIRCLE_SPEED * ((radius + self.WIDTH / 2) / radius)
    #         vr = self.CIRCLE_SPEED * ((radius - self.WIDTH / 2) / radius)
    #         self.setSpeed(vl, vr)
    #         self.addLineDistance()
    #     else:
    #         self.setSpeed(0, 0)
    #         self.totalDistance = 0.0
    #         self.circleFinished = True

    # 机器人画一个圆、半圆或1/4圆(向机器人的左边/右边画)
    def circle(self, radius, c_type, direction):
        if self.circleFinished:
            return
        if self.startPos is None:
            # 初始化机器人的位置
            self.startPos = [self.gps.getValues()[0], self.gps.getValues()[2]]
            # 初始化机器人面向的角度
            self.startAngle = self.imu.getRollPitchYaw()[2]
        # 机器人需要走过的距离
        distance = 0
        # 机器人与终点的距离(用于判断画圆是否完成)
        distanceToEnd = 0
        # 机器人最小要走过的距离(用于结束位置的判断和确定)
        minDis = radius * math.pi * 0.3
        # 当前机器人的位置
        nowPos = [self.gps.getValues()[0], self.gps.getValues()[2]]
        if c_type == CircleType.CIRCLE:
            distanceToEnd = pow(pow(nowPos[0] - self.startPos[0], 2) + pow(nowPos[1] - self.startPos[1], 2), 0.5)
            distance = radius * math.pi * 2
        else:
            # 机器人转过后的角度
            if direction == Direction.LEFT:
                radiusAngle = self.startAngle + math.pi / 2
            else:
                radiusAngle = self.startAngle - math.pi / 2
            # # 处理从调整后角度大于3.14的情况,将其调整回负向角
            # if direction == Direction.LEFT and radiusAngle > math.pi:
            #     radiusAngle = - (math.pi - (math.pi / 2 - (math.pi - self.startAngle)))
            # # 处理从调整后角度小于-3.14的情况,将其调整回正向角
            # if direction == Direction.RIGHT and radiusAngle < -math.pi:
            #     radiusAngle = math.pi - (math.pi / 2 - (self.startAngle + math.pi))
            if c_type == CircleType.SEMI:
                endPos = [self.startPos[0] - math.sin(radiusAngle) * 2 * radius,
                          self.startPos[1] - math.cos(radiusAngle) * 2 * radius]
                distance = radius * math.pi
            else:
                endPos = [self.startPos[0] - math.sin(radiusAngle) * radius - math.sin(self.startAngle) * radius,
                          self.startPos[1] + math.cos(radiusAngle) * radius - math.cos(self.startAngle) * radius]
                distance = radius * math.pi / 2
            distanceToEnd = pow(pow(nowPos[0] - endPos[0], 2) + pow(nowPos[1] - endPos[1], 2), 0.5)

        # 用圆的周长来对画过的距离进行限定，防止无限循环
        if self.totalDistance < distance:
            # 如果与起始点的距离小于2cm就认为画圆完成，停止机器人的运动
            if self.totalDistance > minDis and distanceToEnd < 0.015:
                self.setSpeed(0, 0)
                self.lastStepTime = -1.0
                self.totalDistance = 0.0
                self.startAngle = -100.0
                self.startPos = None
                self.circleFinished = True
                return
            if direction == Direction.LEFT:
                vl = self.CIRCLE_SPEED * ((radius - self.WIDTH / 2) / radius)
                vr = self.CIRCLE_SPEED * ((radius + self.WIDTH / 2) / radius)
            else:
                vl = self.CIRCLE_SPEED * ((radius + self.WIDTH / 2) / radius)
                vr = self.CIRCLE_SPEED * ((radius - self.WIDTH / 2) / radius)
            self.setSpeed(vl, vr)
            self.addLineDistance()
        else:
            self.setSpeed(0, 0)
            self.totalDistance = 0.0
            self.lastStepTime = -1.0
            self.startAngle = -100.0
            self.startPos = None
            self.circleFinished = True

    # 机器人画给定长宽的矩形，执行玩一个步骤就累加rectangleStep的值以执行下一个步骤
    def paintRectangle(self, length, width):
        if self.rectangleFinished:
            return
        if self.rectangleStep == 1:
            # 启用画笔
            self.pen.write(True)
            self.goFinished = False
            self.goStraight(length)
            if self.goFinished:
                self.turnFinished = False
                self.rectangleStep = 2
        elif self.rectangleStep == 2:
            self.turn(Direction.RIGHT, math.pi / 2)
            if self.turnFinished:
                self.goFinished = False
                self.rectangleStep = 3
        elif self.rectangleStep == 3:
            self.goStraight(width)
            if self.goFinished:
                self.turnFinished = False
                self.rectangleStep = 4
        elif self.rectangleStep == 4:
            self.turn(Direction.RIGHT, math.pi / 2)
            if self.turnFinished:
                self.goFinished = False
                self.rectangleStep = 5
        elif self.rectangleStep == 5:
            self.goStraight(length)
            if self.goFinished:
                self.turnFinished = False
                self.rectangleStep = 6
        elif self.rectangleStep == 6:
            self.turn(Direction.RIGHT, math.pi / 2)
            if self.turnFinished:
                self.goFinished = False
                self.rectangleStep = 7
        elif self.rectangleStep == 7:
            self.goStraight(width)
            if self.goFinished:
                self.turnFinished = False
                self.rectangleStep = 8
        else:
            self.turn(Direction.RIGHT, math.pi / 2)
            if self.turnFinished:
                self.rectangleStep = 1
                self.pen.write(False)
                self.rectangleFinished = True

    # 机器人画给定长宽的五人制足球场，执行玩一个步骤就累加footballFieldStep的值以执行下一个步骤
    def paintFootballField(self, length, width):
        if self.footballFieldFinished:
            return
        if self.footballFieldStep == 0:
            self.turnFinished = False
            self.turn(Direction.LEFT, math.pi / 2)
            if self.turnFinished:
                self.footballPos = [self.gps.getValues()[0], self.gps.getValues()[2]]
                self.goFinished = False
                self.footballFieldStep = 1
        elif self.footballFieldStep == 1:
            self.pen.write(True)
            self.goStraight(length / 2)
            if self.goFinished:
                self.turnFinished = False
                self.footballFieldStep = 2
        elif self.footballFieldStep == 2:
            self.turn(Direction.RIGHT, math.pi / 2)
            if self.turnFinished:
                self.goFinished = False
                self.footballFieldStep = 3
        elif self.footballFieldStep == 3:
            self.goStraight(self.FLAG_RADIUS)
            if self.goFinished:
                self.turnFinished = False
                self.footballFieldStep = 4
        elif self.footballFieldStep == 4:
            self.turn(Direction.RIGHT, math.pi / 2)
            if self.turnFinished:
                self.circleFinished = False
                self.footballFieldStep = 5
        elif self.footballFieldStep == 5:
            self.circle(self.FLAG_RADIUS, CircleType.QUARTER, Direction.RIGHT)
            if self.circleFinished:
                self.circleFinished = False
                self.pen.write(False)
                self.footballFieldStep = 6
        elif self.footballFieldStep == 6:
            self.circle(self.FLAG_RADIUS, CircleType.SEMI, Direction.RIGHT)
            if self.circleFinished:
                self.circleFinished = False
                self.footballFieldStep = 7
        elif self.footballFieldStep == 7:
            self.circle(self.FLAG_RADIUS, CircleType.QUARTER, Direction.RIGHT)
            if self.circleFinished:
                self.turnFinished = False
                self.footballFieldStep = 8
        elif self.footballFieldStep == 8:
            self.turn(Direction.LEFT, math.pi / 2)
            if self.turnFinished:
                self.goFinished = False
                self.pen.write(True)
                self.footballFieldStep = 9
        elif self.footballFieldStep == 9:
            self.goStraight(width * 4 / 5 - self.FLAG_RADIUS)
            if self.goFinished:
                self.turnFinished = False
                self.footballFieldStep = 10
        elif self.footballFieldStep == 10:
            self.turn(Direction.RIGHT, math.pi / 2)
            if self.turnFinished:
                self.circleFinished = False
                self.footballFieldStep = 11
        elif self.footballFieldStep == 11:
            self.circle(width * 1 / 5, CircleType.QUARTER, Direction.RIGHT)
            if self.circleFinished:
                self.goFinished = False
                self.footballFieldStep = 12
        elif self.footballFieldStep == 12:
            self.goStraight(width * 1 / 5)
            if self.goFinished:
                self.circleFinished = False
                self.footballFieldStep = 13
        elif self.footballFieldStep == 13:
            self.circle(width * 1 / 5, CircleType.QUARTER, Direction.RIGHT)
            if self.circleFinished:
                self.turnFinished = False
                self.footballFieldStep = 14
        elif self.footballFieldStep == 14:
            self.turn(Direction.RIGHT, math.pi / 2)
            if self.turnFinished:
                self.goFinished = False
                self.pen.write(False)
                self.footballFieldStep = 15
        elif self.footballFieldStep == 15:
            self.goStraight(width * 3 / 5)
            if self.goFinished:
                self.goFinished = False
                self.pen.write(True)
                self.footballFieldStep = 16
        elif self.footballFieldStep == 16:
            self.goStraight(width * 1 / 5)
            if self.goFinished:
                self.turnFinished = False
                self.footballFieldStep = 17
        elif self.footballFieldStep == 17:
            self.turn(Direction.RIGHT, math.pi / 2)
            if self.turnFinished:
                self.goFinished = False
                self.footballFieldStep = 18
        elif self.footballFieldStep == 18:
            self.goStraight(self.FLAG_RADIUS)
            if self.goFinished:
                self.turnFinished = False
                self.footballFieldStep = 19
        elif self.footballFieldStep == 19:
            self.turn(Direction.RIGHT, math.pi / 2)
            if self.turnFinished:
                self.circleFinished = False
                self.footballFieldStep = 20
        elif self.footballFieldStep == 20:
            self.circle(self.FLAG_RADIUS, CircleType.QUARTER, Direction.RIGHT)
            if self.circleFinished:
                self.circleFinished = False
                self.pen.write(False)
                self.footballFieldStep = 21
        elif self.footballFieldStep == 21:
            self.circle(self.FLAG_RADIUS, CircleType.SEMI, Direction.RIGHT)
            if self.circleFinished:
                self.circleFinished = False
                self.footballFieldStep = 22
        elif self.footballFieldStep == 22:
            self.circle(self.FLAG_RADIUS, CircleType.QUARTER, Direction.RIGHT)
            if self.circleFinished:
                self.turnFinished = False
                self.footballFieldStep = 23
        elif self.footballFieldStep == 23:
            self.turn(Direction.LEFT, math.pi / 2)
            if self.turnFinished:
                self.goFinished = False
                self.pen.write(True)
                self.footballFieldStep = 24
        elif self.footballFieldStep == 24:
            self.goStraight(length / 2 - self.FLAG_RADIUS)
            if self.goFinished:
                self.turnFinished = False
                self.footballFieldStep = 25
        elif self.footballFieldStep == 25:
            self.turn(Direction.RIGHT, math.pi / 2)
            if self.turnFinished:
                self.goFinished = False
                self.footballFieldStep = 26
        elif self.footballFieldStep == 26:
            self.goStraight(width * 2 / 3)
            if self.goFinished:
                self.turnFinished = False
                self.footballFieldStep = 27
        elif self.footballFieldStep == 27:
            self.turn(Direction.RIGHT, math.pi / 2)
            if self.turnFinished:
                self.circleFinished = False
                self.footballFieldStep = 28
        elif self.footballFieldStep == 28:
            self.circle(width / 6, CircleType.CIRCLE, Direction.RIGHT)
            if self.circleFinished:
                self.turnFinished = False
                self.footballFieldStep = 29
        elif self.footballFieldStep == 29:
            self.turn(Direction.LEFT, math.pi / 2)
            if self.turnFinished:
                self.goFinished = False
                self.footballFieldStep = 30
                self.footballNPos = [self.gps.getValues()[0], self.gps.getValues()[2]]
        elif self.footballFieldStep == 30:
            distanceReturn = pow(pow(self.footballNPos[0] - self.footballPos[0], 2) +
                                 pow(self.footballNPos[1] - self.footballPos[1], 2), 0.5)
            self.goStraight(distanceReturn)
            if self.goFinished:
                self.turnFinished = False
                self.footballPos = None
                self.footballNPos = None
                self.footballFieldStep = 31
        elif self.footballFieldStep == 31:
            self.turn(Direction.LEFT, math.pi / 2)
            if self.turnFinished:
                self.goFinished = False
                self.footballFieldStep = 32
        if self.footballFieldStep == 32:
            self.pen.write(True)
            self.goStraight(length / 2)
            if self.goFinished:
                self.turnFinished = False
                self.footballFieldStep = 33
        elif self.footballFieldStep == 33:
            self.turn(Direction.LEFT, math.pi / 2)
            if self.turnFinished:
                self.goFinished = False
                self.footballFieldStep = 34
        elif self.footballFieldStep == 34:
            self.goStraight(self.FLAG_RADIUS)
            if self.goFinished:
                self.turnFinished = False
                self.footballFieldStep = 35
        elif self.footballFieldStep == 35:
            self.turn(Direction.LEFT, math.pi / 2)
            if self.turnFinished:
                self.circleFinished = False
                self.footballFieldStep = 36
        elif self.footballFieldStep == 36:
            self.circle(self.FLAG_RADIUS, CircleType.QUARTER, Direction.LEFT)
            if self.circleFinished:
                self.circleFinished = False
                self.pen.write(False)
                self.footballFieldStep = 37
        elif self.footballFieldStep == 37:
            self.circle(self.FLAG_RADIUS, CircleType.SEMI, Direction.LEFT)
            if self.circleFinished:
                self.circleFinished = False
                self.footballFieldStep = 38
        elif self.footballFieldStep == 38:
            self.circle(self.FLAG_RADIUS, CircleType.QUARTER, Direction.LEFT)
            if self.circleFinished:
                self.turnFinished = False
                self.pen.write(False)
                self.footballFieldStep = 39
        elif self.footballFieldStep == 39:
            self.turn(Direction.RIGHT, math.pi / 2)
            if self.turnFinished:
                self.goFinished = False
                self.pen.write(True)
                self.footballFieldStep = 40
        elif self.footballFieldStep == 40:
            self.goStraight(width * 4 / 5 - self.FLAG_RADIUS)
            if self.goFinished:
                self.turnFinished = False
                self.footballFieldStep = 41
        elif self.footballFieldStep == 41:
            self.turn(Direction.LEFT, math.pi / 2)
            if self.turnFinished:
                self.circleFinished = False
                self.footballFieldStep = 42
        elif self.footballFieldStep == 42:
            self.circle(width * 1 / 5, CircleType.QUARTER, Direction.LEFT)
            if self.circleFinished:
                self.goFinished = False
                self.footballFieldStep = 43
        elif self.footballFieldStep == 43:
            self.goStraight(width * 1 / 5)
            if self.goFinished:
                self.circleFinished = False
                self.footballFieldStep = 44
        elif self.footballFieldStep == 44:
            self.circle(width * 1 / 5, CircleType.QUARTER, Direction.LEFT)
            if self.circleFinished:
                self.turnFinished = False
                self.footballFieldStep = 45
        elif self.footballFieldStep == 45:
            self.turn(Direction.LEFT, math.pi / 2)
            if self.turnFinished:
                self.goFinished = False
                self.pen.write(False)
                self.footballFieldStep = 46
        elif self.footballFieldStep == 46:
            self.goStraight(width * 3 / 5)
            if self.goFinished:
                self.goFinished = False
                self.pen.write(True)
                self.footballFieldStep = 47
        elif self.footballFieldStep == 47:
            self.goStraight(width * 1 / 5)
            if self.goFinished:
                self.turnFinished = False
                self.footballFieldStep = 48
        elif self.footballFieldStep == 48:
            self.turn(Direction.LEFT, math.pi / 2)
            if self.turnFinished:
                self.goFinished = False
                self.footballFieldStep = 49
        elif self.footballFieldStep == 49:
            self.goStraight(self.FLAG_RADIUS)
            if self.goFinished:
                self.turnFinished = False
                self.footballFieldStep = 50
        elif self.footballFieldStep == 50:
            self.turn(Direction.LEFT, math.pi / 2)
            if self.turnFinished:
                self.circleFinished = False
                self.footballFieldStep = 51
        elif self.footballFieldStep == 51:
            self.circle(self.FLAG_RADIUS, CircleType.QUARTER, Direction.LEFT)
            if self.circleFinished:
                self.circleFinished = False
                self.pen.write(False)
                self.footballFieldStep = 52
        elif self.footballFieldStep == 52:
            self.circle(self.FLAG_RADIUS, CircleType.SEMI, Direction.LEFT)
            if self.circleFinished:
                self.circleFinished = False
                self.footballFieldStep = 53
        elif self.footballFieldStep == 53:
            self.circle(self.FLAG_RADIUS, CircleType.QUARTER, Direction.LEFT)
            if self.circleFinished:
                self.turnFinished = False
                self.footballFieldStep = 54
        elif self.footballFieldStep == 54:
            self.turn(Direction.RIGHT, math.pi / 2)
            if self.turnFinished:
                self.goFinished = False
                self.pen.write(True)
                self.footballFieldStep = 55
        elif self.footballFieldStep == 55:
            self.goStraight(length / 2 - self.FLAG_RADIUS)
            if self.goFinished:
                self.footballFieldStep = 0
                self.pen.write(False)
                self.footballFieldFinished = True


myRobot = MyRobot()

while myRobot.robot.step(myRobot.timestep) != -1:
    # myRobot.turn(Direction.LEFT, math.pi / 2)
    # myRobot.paintRectangle(8, 4.9)
    # myRobot.goStraight(20)
    # myRobot.circle(2.35, CircleType.CIRCLE, Direction.LEFT)
    # myRobot.turn(Direction.LEFT, math.pi / 2)
    # 足球场画线时请确保机器人初始位置为(0,10),初始角度为0
    myRobot.paintFootballField(39, 20)
    # myRobot.turn(Direction.LEFT, math.pi)
