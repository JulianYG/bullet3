from scene_stadium import SinglePlayerStadiumScene
from env_bases import MujocoXmlBaseBulletEnv
import numpy as np
from robot_locomotors import Hopper, Walker2D, HalfCheetah, Ant, Humanoid


class WalkerBaseBulletEnv(MujocoXmlBaseBulletEnv):
	def __init__(self, robot):
		MujocoXmlBaseBulletEnv.__init__(self, robot)
		self.camera_x = 0
		self.walk_target_x = 1e3  # kilometer away
		self.walk_target_y = 0

	def create_single_player_scene(self):
		self.stadium_scene = SinglePlayerStadiumScene(gravity=9.8, timestep=0.0165/4, frame_skip=4)
		return self.stadium_scene

	def _reset(self):
		r = MujocoXmlBaseBulletEnv._reset(self)
		self.parts, self.jdict, self.ordered_joints, self.robot_body = self.robot.addToScene(
			self.stadium_scene.ground_plane_mjcf)
		self.ground_ids = set([(self.parts[f].bodies[self.parts[f].bodyIndex], self.parts[f].bodyPartIndex) for f in
							   self.foot_ground_object_names])
		return r

	def move_robot(self, init_x, init_y, init_z):
		"Used by multiplayer stadium to move sideways, to another running lane."
		self.cpp_robot.query_position()
		pose = self.cpp_robot.root_part.pose()
		pose.move_xyz(init_x, init_y, init_z)  # Works because robot loads around (0,0,0), and some robots have z != 0 that is left intact
		self.cpp_robot.set_pose(pose)

	electricity_cost	 = -2.0	# cost for using motors -- this parameter should be carefully tuned against reward for making progress, other values less improtant
	stall_torque_cost	= -0.1	# cost for running electric current through a motor even at zero rotational speed, small
	foot_collision_cost  = -1.0	# touches another leg, or other objects, that cost makes robot avoid smashing feet into itself
	foot_ground_object_names = set(["floor"])  # to distinguish ground and other objects
	joints_at_limit_cost = -0.1	# discourage stuck joints

	def _step(self, a):
		if not self.scene.multiplayer:  # if multiplayer, action first applied to all robots, then global step() called, then _step() for all robots with the same actions
			self.robot.apply_action(a)
			self.scene.global_step()

		state = self.robot.calc_state()  # also calculates self.joints_at_limit

		alive = float(self.robot.alive_bonus(state[0]+self.robot.initial_z, self.robot.body_rpy[1]))   # state[0] is body height above ground, body_rpy[1] is pitch
		done = alive < 0
		if not np.isfinite(state).all():
			print("~INF~", state)
			done = True

		potential_old = self.potential
		self.potential = self.robot.calc_potential()
		progress = float(self.potential - potential_old)

		feet_collision_cost = 0.0
		for i,f in enumerate(self.robot.feet): # TODO: Maybe calculating feet contacts could be done within the robot code
			contact_ids = set((x[2], x[4]) for x in f.contact_list())
			#print("CONTACT OF '%s' WITH %s" % (f.name, ",".join(contact_names)) )
			self.robot.feet_contact[i] = 1.0 if (self.ground_ids & contact_ids) else 0.0
			if contact_ids - self.ground_ids:
				feet_collision_cost += self.foot_collision_cost

		electricity_cost  = self.electricity_cost  * float(np.abs(a*self.robot.joint_speeds).mean())  # let's assume we have DC motor with controller, and reverse current braking
		electricity_cost += self.stall_torque_cost * float(np.square(a).mean())

		joints_at_limit_cost = float(self.joints_at_limit_cost * self.robot.joints_at_limit)

		self.rewards = [
			alive,
			progress,
			electricity_cost,
			joints_at_limit_cost,
			feet_collision_cost
			]

		self.HUD(state, a, done)
		return state, sum(self.rewards), bool(done), {}

	def camera_adjust(self):
		x, y, z = self.body_xyz
		self.camera_x = 0.98*self.camera_x + (1-0.98)*x
		self.camera.move_and_look_at(self.camera_x, y-2.0, 1.4, x, y, 1.0)

class HopperBulletEnv(WalkerBaseBulletEnv):
	def __init__(self):
		self.robot = Hopper()
		WalkerBaseBulletEnv.__init__(self, self.robot)

class Walker2DBulletEnv(WalkerBaseBulletEnv):
	def __init__(self):
		self.robot = Walker2D()
		WalkerBaseBulletEnv.__init__(self, self.robot)

class HalfCheetahBulletEnv(WalkerBaseBulletEnv):
	def __init__(self):
		self.robot = HalfCheetah()
		WalkerBaseBulletEnv.__init__(self, self.robot)

class AntBulletEnv(WalkerBaseBulletEnv):
	def __init__(self):
		self.robot = Ant()
		WalkerBaseBulletEnv.__init__(self, self.robot)

class HumanoidBulletEnv(WalkerBaseBulletEnv):
	def __init__(self):
		self.robot = Humanoid()
		WalkerBaseBulletEnv.__init__(self, self.robot)
		self.electricity_cost  = 4.25*WalkerBaseBulletEnv.electricity_cost
		self.stall_torque_cost = 4.25*WalkerBaseBulletEnv.stall_torque_cost
