from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *
import sys
import random
import time
import math

# ============================================================================
# CONSTANTS AND CONFIGURATION
# ============================================================================

WIN_W, WIN_H = 1280, 720
GAME_TITLE = b"SkyStrike - Aerial Combat Simulation"

# Game boundaries
WORLD_SIZE = 500
WORLD_HEIGHT_MIN = 0
WORLD_HEIGHT_MAX = 400

# Player constants
PLAYER_SPEED = 80.0
PLAYER_TURN_SPEED = 2.0
PLAYER_MAX_HEALTH = 100
PLAYER_MACHINE_GUN_COOLDOWN = 0.08
PLAYER_MISSILE_COOLDOWN = 1.5

# Enemy constants
ENEMY_SPAWN_INTERVAL = 3.0
MAX_ENEMIES = 15

# Difficulty scaling
DIFFICULTY_SCALE_RATE = 0.05

# ============================================================================
# UTILITY CLASSES
# ============================================================================



class Vector3:
    """3D vector math operations"""
    def __init__(self, x=0, y=0, z=0):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)
    
    def __add__(self, other):
        return Vector3(self.x + other.x, self.y + other.y, self.z + other.z)
    
    def __sub__(self, other):
        return Vector3(self.x - other.x, self.y - other.y, self.z - other.z)
    
    def __mul__(self, scalar):
        return Vector3(self.x * scalar, self.y * scalar, self.z * scalar)
    
    def length(self):
        return math.sqrt(self.x**2 + self.y**2 + self.z**2)
    
    def normalize(self):
        l = self.length()
        if l > 0:
            return Vector3(self.x/l, self.y/l, self.z/l)
        return Vector3(0, 0, 0)
    
    def distance_to(self, other):
        return (self - other).length()
    
    def copy(self):
        return Vector3(self.x, self.y, self.z)



# ============================================================================
# GAME STATE ENUM
# ============================================================================

class GameState:
    MENU = 0
    MISSION_SELECT = 1
    MISSION_BRIEFING = 2
    PLAYING = 3
    PAUSED = 4
    MISSION_COMPLETE = 5
    MISSION_FAILED = 6
    GAME_OVER = 7

# ============================================================================
# MISSION SYSTEM
# ============================================================================

class MissionType:
    ELIMINATION = 0
    SURVIVAL = 1
    ESCORT = 2
    DEFENSE = 3
    BOSS = 4

class Mission:
    """Mission definition"""
    def __init__(self, mission_id, name, mission_type, description, objectives):
        self.id = mission_id
        self.name = name
        self.type = mission_type
        self.description = description
        self.objectives = objectives  # Dict with mission-specific data
        self.completed = False
        self.unlocked = (mission_id == 0)  # First mission unlocked by default

# Define all missions
MISSIONS = [
    Mission(0, "First Contact", MissionType.ELIMINATION,
            "Destroy 3 Scout Drones",
            {"target_type": "scout", "target_count": 3}),
    
    Mission(1, "Survival Test", MissionType.SURVIVAL,
            "Survive for 60 seconds",
            {"duration": 60}),
    
    Mission(2, "Strike Force", MissionType.ELIMINATION,
            "Destroy 5 Attack Jets",
            {"target_type": "jet", "target_count": 5}),
    
    Mission(3, "Escort Duty", MissionType.ESCORT,
            "Protect the transport aircraft",
            {"escort_health": 100, "escort_speed": 40}),
    
    Mission(4, "Base Defense", MissionType.DEFENSE,
            "Stop 10 enemies from reaching the base",
            {"max_breaches": 3, "enemy_waves": 10}),
    
    Mission(5, "Ace Showdown", MissionType.BOSS,
            "Defeat the enemy Ace Pilot",
            {"boss_health": 400, "boss_type": "jet"}),
    
    Mission(6, "Final Assault", MissionType.ELIMINATION,
            "Destroy 3 Bombers and 5 Jets",
            {"targets": {"bomber": 3, "jet": 5}}),
]

# ============================================================================
# EXPLOSION EFFECT
# ============================================================================

class Explosion:
    """Visual explosion effect"""
    def __init__(self, position):
        self.position = position.copy()
        self.age = 0
        self.max_age = 1.0
        self.size = 5
        self.max_size = 30
    
    def update(self, dt):
        self.age += dt
        progress = self.age / self.max_age
        self.size = self.max_size * progress
        return self.age < self.max_age
    
    def render(self):
        progress = self.age / self.max_age
        alpha = 1.0 - progress
        
        glPushMatrix()
        glTranslatef(self.position.x, self.position.y, self.position.z)
        
        # Outer sphere (orange)
        glColor4f(1.0, 0.5, 0.0, alpha * 0.7)
        glutSolidSphere(self.size, 8, 8)
        
        # Inner sphere (yellow)
        glColor4f(1.0, 1.0, 0.0, alpha)
        glutSolidSphere(self.size * 0.6, 8, 8)
        
        glPopMatrix()

# ============================================================================
# FRIENDLY AIRCRAFT (for Escort missions)
# ============================================================================

class FriendlyAircraft:
    """Friendly aircraft that needs protection"""
    def __init__(self, start_pos, speed=40):
        self.position = start_pos.copy()
        self.speed = speed
        self.health = 100
        self.max_health = 100
        self.alive = True
        self.reached_destination = False
        # Flies straight forward
        self.direction = Vector3(1, 0, 0).normalize()
        self.destination = Vector3(WORLD_SIZE * 0.8, 100, 0)
    
    def update(self, dt):
        if not self.alive or self.reached_destination:
            return
        
        # Move toward destination
        to_dest = (self.destination - self.position)
        if to_dest.length() < 10:
            self.reached_destination = True
            return
        
        self.direction = to_dest.normalize()
        self.position = self.position + self.direction * self.speed * dt
    
    def take_damage(self, damage):
        self.health -= damage
        if self.health <= 0:
            self.health = 0
            self.alive = False
            return True
        return False
    
    def render(self):
        if not self.alive:
            return
        
        glPushMatrix()
        glTranslatef(self.position.x, self.position.y, self.position.z)
        
        # Friendly aircraft (green color)
        glColor3f(0.2, 0.8, 0.3)
        glPushMatrix()
        glScalef(5, 3, 12)
        glutSolidCube(1)
        glPopMatrix()
        
        # Wings
        glColor3f(0.15, 0.7, 0.25)
        glPushMatrix()
        glScalef(20, 0.8, 5)
        glutSolidCube(1)
        glPopMatrix()
        
        # Health bar
        glPushMatrix()
        glTranslatef(0, 8, 0)
        health_percent = self.health / self.max_health
        glColor3f(0, 1, 0) if health_percent > 0.5 else glColor3f(1, 1, 0)
        glBegin(GL_QUADS)
        glVertex3f(-5, 0, 0)
        glVertex3f(-5 + 10 * health_percent, 0, 0)
        glVertex3f(-5 + 10 * health_percent, 1, 0)
        glVertex3f(-5, 1, 0)
        glEnd()
        glPopMatrix()
        
        glPopMatrix()

# ============================================================================
# DEFENSE BASE (for Defense missions)
# ============================================================================

class DefenseBase:
    """Base that needs to be defended"""
    def __init__(self):
        self.position = Vector3(0, 50, 0)
        self.size = 30
        self.breach_radius = 100  # Enemies within this radius count as breach
        self.breaches = 0
    
    def check_breach(self, enemy_position):
        """Check if enemy has breached the defense perimeter"""
        dist = self.position.distance_to(enemy_position)
        return dist < self.breach_radius
    
    def render(self):
        glPushMatrix()
        glTranslatef(self.position.x, self.position.y, self.position.z)
        
        # Base structure (large cube)
        glColor3f(0.3, 0.3, 0.4)
        glPushMatrix()
        glScalef(self.size, self.size * 0.5, self.size)
        glutSolidCube(1)
        glPopMatrix()
        
        # Tower
        glColor3f(0.4, 0.4, 0.5)
        glPushMatrix()
        glTranslatef(0, self.size * 0.5, 0)
        glScalef(10, 20, 10)
        glutSolidCube(1)
        glPopMatrix()
        
        # Defense perimeter indicator (transparent)
        glColor4f(0.2, 0.5, 1.0, 0.2)
        glPushMatrix()
        glTranslatef(0, -self.size * 0.25, 0)
        glutSolidSphere(self.breach_radius, 16, 16)
        glPopMatrix()
        
        glPopMatrix()

# ============================================================================
# CLOUD SYSTEM
# ============================================================================

class Cloud:
    """Environmental cloud object"""
    def __init__(self):
        self.position = Vector3(
            random.uniform(-WORLD_SIZE, WORLD_SIZE),
            random.uniform(100, 300),
            random.uniform(-WORLD_SIZE, WORLD_SIZE)
        )
        self.size = random.uniform(15, 40)
        self.velocity = Vector3(random.uniform(-5, 5), 0, random.uniform(-5, 5))
    
    def update(self, dt):
        self.position = self.position + self.velocity * dt
        
        # Wrap around world
        if abs(self.position.x) > WORLD_SIZE:
            self.position.x = -self.position.x
        if abs(self.position.z) > WORLD_SIZE:
            self.position.z = -self.position.z
    
    def render(self):
        glPushMatrix()
        glTranslatef(self.position.x, self.position.y, self.position.z)
        glColor4f(0.9, 0.9, 0.95, 0.6)
        
        # Multiple spheres for cloud shape
        glutSolidSphere(self.size, 8, 8)
        glTranslatef(self.size * 0.6, 0, 0)
        glutSolidSphere(self.size * 0.8, 8, 8)
        glTranslatef(-self.size * 1.2, 0, 0)
        glutSolidSphere(self.size * 0.7, 8, 8)
        
        glPopMatrix()

# ============================================================================
# PROJECTILE SYSTEM
# ============================================================================

class Projectile:
    """Bullets and missiles"""
    def __init__(self, position, direction, speed, damage, is_missile=False, owner="player"):
        self.position = position.copy()
        self.direction = direction.normalize()
        self.speed = speed
        self.damage = damage
        self.is_missile = is_missile
        self.owner = owner
        self.alive = True
        self.lifetime = 0
        self.max_lifetime = 5.0
        self.target = None
    
    def update(self, dt, enemies=None):
        self.lifetime += dt
        if self.lifetime > self.max_lifetime:
            self.alive = False
            return
        
        # Homing behavior for missiles
        if self.is_missile and enemies and self.owner == "player":
            # Find nearest enemy
            nearest = None
            min_dist = float('inf')
            for enemy in enemies:
                if enemy.alive:
                    dist = self.position.distance_to(enemy.position)
                    if dist < min_dist:
                        min_dist = dist
                        nearest = enemy
            
            if nearest:
                # Adjust direction toward target
                to_target = (nearest.position - self.position).normalize()
                # More aggressive homing - blend current direction with target direction
                self.direction = (self.direction * 0.85 + to_target * 0.15).normalize()
        
        # Move projectile
        self.position = self.position + self.direction * self.speed * dt
        
        # Check world bounds
        if (abs(self.position.x) > WORLD_SIZE or 
            abs(self.position.z) > WORLD_SIZE or
            self.position.y < 0 or self.position.y > WORLD_HEIGHT_MAX):
            self.alive = False
    
    def render(self):
        glPushMatrix()
        glTranslatef(self.position.x, self.position.y, self.position.z)
        
        if self.is_missile:
            # Missile (cylinder with cone)
            glColor3f(0.8, 0.2, 0.2)
            quad = gluNewQuadric()
            glRotatef(-90, 1, 0, 0)
            gluCylinder(quad, 1, 1, 6, 8, 1)
            glTranslatef(0, 0, 6)
            glutSolidCone(1.5, 3, 8, 1)
            gluDeleteQuadric(quad)
        else:
            # Bullet (small sphere)
            if self.owner == "player":
                glColor3f(1.0, 1.0, 0.0)
            else:
                glColor3f(1.0, 0.3, 0.0)
            glutSolidSphere(1, 6, 6)
        
        glPopMatrix()




class EnemyState:
    PATROL = 0
    CHASE = 1
    ATTACK = 2
    EVADE = 3
    DESTROYED = 4

class Enemy:
    """Enemy aircraft with AI"""
    def __init__(self, enemy_type="scout"):
        self.type = enemy_type
        self.position = Vector3(
            random.choice([-WORLD_SIZE, WORLD_SIZE]) * random.uniform(0.5, 1.0),
            random.uniform(50, 300),
            random.choice([-WORLD_SIZE, WORLD_SIZE]) * random.uniform(0.5, 1.0)
        )
        self.velocity = Vector3(0, 0, 0)
        self.rotation = random.uniform(0, 360)
        self.state = EnemyState.PATROL
        self.alive = True
        
        # Type-specific attributes
        if enemy_type == "scout":
            self.max_health = 30
            self.speed = 60
            self.size = 8
            self.color = (0.3, 0.8, 1.0)
            self.fire_cooldown_max = 2.0
            self.damage = 5
        elif enemy_type == "jet":
            self.max_health = 60
            self.speed = 45
            self.size = 10
            self.color = (1.0, 0.3, 0.3)
            self.fire_cooldown_max = 1.0
            self.damage = 10
        else:  # bomber
            self.max_health = 100
            self.speed = 30
            self.size = 15
            self.color = (0.5, 0.5, 0.5)
            self.fire_cooldown_max = 1.5
            self.damage = 15
        
        self.health = self.max_health
        self.fire_cooldown = 0
        self.patrol_target = self._new_patrol_target()
        self.state_timer = 0
    
    def _new_patrol_target(self):
        return Vector3(
            random.uniform(-WORLD_SIZE * 0.8, WORLD_SIZE * 0.8),
            random.uniform(50, 300),
            random.uniform(-WORLD_SIZE * 0.8, WORLD_SIZE * 0.8)
        )
    
    def update(self, dt, player_pos, difficulty_multiplier):
        if not self.alive:
            return None
        
        self.fire_cooldown = max(0, self.fire_cooldown - dt)
        self.state_timer += dt
        
        dist_to_player = self.position.distance_to(player_pos)
        
        # State transitions
        if self.health < self.max_health * 0.3:
            self.state = EnemyState.EVADE
        elif dist_to_player < 100:
            self.state = EnemyState.ATTACK
        elif dist_to_player < 200:
            self.state = EnemyState.CHASE
        else:
            self.state = EnemyState.PATROL
        
        # Behavior based on state
        target_pos = None
        
        if self.state == EnemyState.PATROL:
            if self.position.distance_to(self.patrol_target) < 20:
                self.patrol_target = self._new_patrol_target()
            target_pos = self.patrol_target
        
        elif self.state == EnemyState.CHASE:
            target_pos = player_pos
        
        elif self.state == EnemyState.ATTACK:
            # Circle around player
            angle = self.state_timer
            offset = Vector3(math.cos(angle) * 80, 0, math.sin(angle) * 80)
            target_pos = player_pos + offset
        
        elif self.state == EnemyState.EVADE:
            # Move away from player
            away = (self.position - player_pos).normalize()
            target_pos = self.position + away * 100
        
        # Move toward target
        if target_pos:
            direction = (target_pos - self.position).normalize()
            speed = self.speed * difficulty_multiplier
            self.velocity = direction * speed
            self.position = self.position + self.velocity * dt
            
            # Update rotation to face direction
            if direction.length() > 0:
                self.rotation = math.degrees(math.atan2(direction.x, direction.z))
        
        # Constrain to world bounds
        self.position.x = max(-WORLD_SIZE, min(WORLD_SIZE, self.position.x))
        self.position.y = max(WORLD_HEIGHT_MIN + 20, min(WORLD_HEIGHT_MAX - 20, self.position.y))
        self.position.z = max(-WORLD_SIZE, min(WORLD_SIZE, self.position.z))
        
        # Fire at player
        if self.state == EnemyState.ATTACK and self.fire_cooldown == 0:
            self.fire_cooldown = self.fire_cooldown_max / difficulty_multiplier
            # Predict player position
            to_player = (player_pos - self.position).normalize()
            return Projectile(self.position, to_player, 100, self.damage, False, "enemy")
        
        return None
    
    def take_damage(self, damage):
        self.health -= damage
        if self.health <= 0:
            self.alive = False
            return True
        return False
    
    def render(self):
        if not self.alive:
            return
        
        glPushMatrix()
        glTranslatef(self.position.x, self.position.y, self.position.z)
        glRotatef(self.rotation, 0, 1, 0)
        
        # Fuselage
        glColor3f(*self.color)
        glPushMatrix()
        glScalef(3, 2, self.size)
        glutSolidCube(1)
        glPopMatrix()
        
        # Wings
        glColor3f(self.color[0] * 0.8, self.color[1] * 0.8, self.color[2] * 0.8)
        glPushMatrix()
        glTranslatef(0, 0, 0)
        glScalef(self.size * 1.5, 0.5, 4)
        glutSolidCube(1)
        glPopMatrix()
        
        # Engines
        glColor3f(0.3, 0.3, 0.3)
        quad = gluNewQuadric()
        glPushMatrix()
        glTranslatef(3, -1, -self.size * 0.4)
        glRotatef(90, 0, 1, 0)
        gluCylinder(quad, 1, 1, 2, 8, 1)
        glPopMatrix()
        
        glPushMatrix()
        glTranslatef(-3, -1, -self.size * 0.4)
        glRotatef(90, 0, 1, 0)
        gluCylinder(quad, 1, 1, 2, 8, 1)
        glPopMatrix()
        gluDeleteQuadric(quad)
        
        # Health bar
        glPushMatrix()
        glTranslatef(0, self.size + 5, 0)
        glRotatef(-self.rotation, 0, 1, 0)
        health_percent = self.health / self.max_health
        if health_percent > 0.6:
            glColor3f(0, 1, 0)
        elif health_percent > 0.3:
            glColor3f(1, 1, 0)
        else:
            glColor3f(1, 0, 0)
        glBegin(GL_QUADS)
        glVertex3f(-5, 0, 0)
        glVertex3f(-5 + 10 * health_percent, 0, 0)
        glVertex3f(-5 + 10 * health_percent, 1, 0)
        glVertex3f(-5, 1, 0)
        glEnd()
        glPopMatrix()
        
        glPopMatrix()













class CameraMode:
    CHASE = 0
    COCKPIT = 1
    TACTICAL = 2
    ORBIT = 3

class CameraManager:
    """Multi-mode camera system"""
    def __init__(self):
        self.mode = CameraMode.CHASE
        self.orbit_angle = 0
    
    def apply(self, player):
        if self.mode == CameraMode.CHASE:
            # Third-person chase camera
            rad = math.radians(player.rotation)
            offset_dist = 40
            offset_height = 15
            
            cam_x = player.position.x - math.sin(rad) * offset_dist
            cam_y = player.position.y + offset_height
            cam_z = player.position.z - math.cos(rad) * offset_dist
            
            gluLookAt(
                cam_x, cam_y, cam_z,
                player.position.x, player.position.y, player.position.z,
                0, 1, 0
            )
        
        elif self.mode == CameraMode.COCKPIT:
            # First-person cockpit view - adjusted to be inside the "cockpit"
            # Slightly back from the nose to see the frame
            forward = player.get_forward_direction()
            
            # Position camera inside the hypothetical cockpit
            # Taking player rotation into account
            rad_yaw = math.radians(player.rotation)
            rad_pitch = math.radians(player.pitch)
            
            # Offset from center
            cam_offset = Vector3(0, 3, 2)
            
            # Apply rotation to offset
            # Simple rotation logic for the offset
            rx = cam_offset.x * math.cos(rad_yaw) - cam_offset.z * math.sin(rad_yaw)
            rz = cam_offset.x * math.sin(rad_yaw) + cam_offset.z * math.cos(rad_yaw)
            
            cam_x = player.position.x + rx
            cam_y = player.position.y + cam_offset.y
            cam_z = player.position.z + rz
            
            # Look forward relative to player
            look_target = player.position + forward * 50
            
            gluLookAt(
                cam_x, cam_y, cam_z,
                look_target.x, look_target.y, look_target.z,
                0, 1, 0
            )
        
        elif self.mode == CameraMode.TACTICAL:
            # Top-down tactical view
            gluLookAt(
                player.position.x, player.position.y + 200, player.position.z,
                player.position.x, player.position.y, player.position.z,
                0, 0, -1
            )
        
        elif self.mode == CameraMode.ORBIT:
            # Cinematic orbit camera
            self.orbit_angle += 0.5
            radius = 100
            rad = math.radians(self.orbit_angle)
            
            cam_x = player.position.x + math.cos(rad) * radius
            cam_z = player.position.z + math.sin(rad) * radius
            cam_y = player.position.y + 30
            
            gluLookAt(
                cam_x, cam_y, cam_z,
                player.position.x, player.position.y, player.position.z,
                0, 1, 0
            )
    
    def cycle(self):
        self.mode = (self.mode + 1) % 4


class SkyStrike:
    """Main game controller"""
    def __init__(self):
        self.state = GameState.MENU
        self.player = PlayerAircraft()
        self.camera = CameraManager()
        self.enemies = []
        self.projectiles = []
        self.explosions = []
        self.clouds = [Cloud() for _ in range(20)]
        
        self.score = 0
        self.combo = 0
        self.combo_timer = 0
        self.shots_fired = 0
        self.shots_hit = 0
        
        self.difficulty_multiplier = 1.0
        self.game_time = 0
        self.enemy_spawn_timer = 0
        
        self.last_time = time.time()
        
        # Debug modes
        self.god_mode = False
        self.auto_aim = False
        
        # Mouse state
        self.mouse_left = False
        self.mouse_right = False
        
        # Mission system
        self.current_mission = None
        self.mission_timer = 0
        self.mission_kills = {}  # Track kills by enemy type
        self.friendly_aircraft = None
        self.defense_base = None
        self.boss_enemy = None
        self.defense_base = None
        self.boss_enemy = None
        self.breached_enemies = set()  # Track enemies that breached defense
        
        # Mission internal counters
        self.mission_enemies_spawned = 0
    
    
    def reset(self):
        """Reset game to initial state"""
        self.player = PlayerAircraft()
        self.enemies = []
        self.projectiles = []
        self.explosions = []
        self.score = 0
        self.combo = 0
        self.combo_timer = 0
        self.shots_fired = 0
        self.shots_hit = 0
        self.difficulty_multiplier = 1.0
        self.game_time = 0
        self.enemy_spawn_timer = 0
        self.mission_timer = 0
        self.mission_kills = {}
        self.friendly_aircraft = None
        self.defense_base = None
        self.boss_enemy = None
        self.breached_enemies = set()
        self.mission_enemies_spawned = 0
        self.state = GameState.PLAYING
    
    def start_mission(self, mission):
        """Start a specific mission"""
        self.reset()
        self.current_mission = mission
        self.mission_timer = 0
        self.mission_kills = {}
        
        # Setup mission-specific objects
        if mission.type == MissionType.ESCORT:
            # Spawn friendly aircraft
            start_pos = Vector3(-WORLD_SIZE * 0.8, 100, 0)
            self.friendly_aircraft = FriendlyAircraft(start_pos, mission.objectives["escort_speed"])
            self.friendly_aircraft.health = mission.objectives["escort_health"]
            self.friendly_aircraft.max_health = mission.objectives["escort_health"]
        
        elif mission.type == MissionType.DEFENSE:
            # Create defense base
            self.defense_base = DefenseBase()
            self.breached_enemies = set()
        
        elif mission.type == MissionType.BOSS:
            # Spawn boss enemy
            boss_type = mission.objectives["boss_type"]
            self.boss_enemy = Enemy(boss_type)
            self.boss_enemy.health = mission.objectives["boss_health"]
            self.boss_enemy.max_health = mission.objectives["boss_health"]
            self.boss_enemy.size *= 1.5  # Make boss bigger
            self.enemies.append(self.boss_enemy)
        
        self.state = GameState.PLAYING
    
    def update(self, dt):
        if self.state == GameState.PLAYING:
            self.game_time += dt
            
            # Mission-specific updates
            if self.current_mission:
                self.mission_timer += dt
                
                # Update friendly aircraft (escort mission)
                if self.friendly_aircraft:
                    self.friendly_aircraft.update(dt)
                    if self.friendly_aircraft.reached_destination:
                        # Mission success!
                        self.state = GameState.MISSION_COMPLETE
                        self.current_mission.completed = True
                        # Unlock next mission
                        if self.current_mission.id < len(MISSIONS) - 1:
                            MISSIONS[self.current_mission.id + 1].unlocked = True
                        return
                    elif not self.friendly_aircraft.alive:
                        # Mission failed
                        self.state = GameState.MISSION_FAILED
                        return
                
                # Check defense breaches
                if self.defense_base:
                    for enemy in self.enemies:
                        if enemy.alive and id(enemy) not in self.breached_enemies:
                            if self.defense_base.check_breach(enemy.position):
                                self.breached_enemies.add(id(enemy))
                                self.defense_base.breaches += 1
                                if self.defense_base.breaches >= self.current_mission.objectives["max_breaches"]:
                                    self.state = GameState.MISSION_FAILED
                                    return
                
                # Mission-specific enemy spawning
                self.enemy_spawn_timer += dt
                spawn_interval = ENEMY_SPAWN_INTERVAL
                
                if self.current_mission.type == MissionType.ELIMINATION:
                    # Spawn specific enemy types for elimination missions
                    if "target_type" in self.current_mission.objectives:
                        target_type = self.current_mission.objectives["target_type"]
                        if self.enemy_spawn_timer > spawn_interval and len(self.enemies) < 5:
                            self.enemy_spawn_timer = 0
                            self.enemies.append(Enemy(target_type))
                            self.mission_enemies_spawned += 1
                    elif "targets" in self.current_mission.objectives:
                        # Multiple target types
                        if self.enemy_spawn_timer > spawn_interval and len(self.enemies) < 8:
                            self.enemy_spawn_timer = 0
                            # Spawn based on what's still needed
                            for etype, count in self.current_mission.objectives["targets"].items():
                                killed = self.mission_kills.get(etype, 0)
                                if killed < count:
                                    self.enemies.append(Enemy(etype))
                                    self.mission_enemies_spawned += 1
                                    break
                
                elif self.current_mission.type == MissionType.SURVIVAL:
                    # Continuous enemy spawning for survival
                    if self.enemy_spawn_timer > spawn_interval / 2 and len(self.enemies) < 10:
                        self.enemy_spawn_timer = 0
                        enemy_type = random.choice(["scout", "jet", "bomber"])
                        self.enemies.append(Enemy(enemy_type))
                    
                    # Check if survived long enough
                    if self.mission_timer >= self.current_mission.objectives["duration"]:
                        self.state = GameState.MISSION_COMPLETE
                        self.current_mission.completed = True
                        if self.current_mission.id < len(MISSIONS) - 1:
                            MISSIONS[self.current_mission.id + 1].unlocked = True
                        return
                
                elif self.current_mission.type == MissionType.ESCORT:
                    # Spawn enemies to attack the escort
                    if self.enemy_spawn_timer > spawn_interval and len(self.enemies) < 6:
                        self.enemy_spawn_timer = 0
                        enemy_type = random.choice(["scout", "jet"])
                        self.enemies.append(Enemy(enemy_type))
                
                elif self.current_mission.type == MissionType.DEFENSE:
                    # Wave-based spawning
                    # Track total spawned against mission requirement
                    total_to_spawn = self.current_mission.objectives["enemy_waves"] * 5 # Assuming 5 per wave roughly or just total count
                    # Adjusting interpretation: "enemy_waves" usually implies total count in similar games or we fix it to mean exact count here
                    # Let's assume enemy_waves is actually "Total Enemies to Defeat" for simplicity in this specific fix
                    
                    if self.mission_enemies_spawned < self.current_mission.objectives["enemy_waves"]:
                        if self.enemy_spawn_timer > spawn_interval and len(self.enemies) < 5:
                            self.enemy_spawn_timer = 0
                            enemy_type = random.choice(["scout", "jet"])
                            self.enemies.append(Enemy(enemy_type))
                            self.mission_enemies_spawned += 1
                    else:
                        # All waves spawned, check if all destroyed
                        if len(self.enemies) == 0:
                            self.state = GameState.MISSION_COMPLETE
                            self.current_mission.completed = True
                            if self.current_mission.id < len(MISSIONS) - 1:
                                MISSIONS[self.current_mission.id + 1].unlocked = True
                            return
                
                elif self.current_mission.type == MissionType.BOSS:
                    # Check if boss is defeated
                    if self.boss_enemy and not self.boss_enemy.alive:
                        self.state = GameState.MISSION_COMPLETE
                        self.current_mission.completed = True
                        if self.current_mission.id < len(MISSIONS) - 1:
                            MISSIONS[self.current_mission.id + 1].unlocked = True
                        return
            else:
                # Free play mode (original behavior)
                self.difficulty_multiplier = 1.0 + self.game_time * DIFFICULTY_SCALE_RATE
                
                # Spawn enemies
                self.enemy_spawn_timer += dt
                spawn_interval = ENEMY_SPAWN_INTERVAL / self.difficulty_multiplier
                if self.enemy_spawn_timer > spawn_interval and len(self.enemies) < MAX_ENEMIES:
                    self.enemy_spawn_timer = 0
                    enemy_type = random.choices(
                        ["scout", "jet", "bomber"],
                        weights=[0.5, 0.3, 0.2]
                    )[0]
                    self.enemies.append(Enemy(enemy_type))
            
            # Update player
            self.player.update(dt)
            
            # Update combo timer
            if self.combo > 0:
                self.combo_timer -= dt
                if self.combo_timer <= 0:
                    self.combo = 0
            
            # Update enemies
            for enemy in self.enemies[:]:
                if enemy.alive:
                    projectile = enemy.update(dt, self.player.position, self.difficulty_multiplier)
                    if projectile:
                        self.projectiles.append(projectile)
                else:
                    self.enemies.remove(enemy)
            
            # Update projectiles
            for proj in self.projectiles[:]:
                proj.update(dt, self.enemies)
                if not proj.alive:
                    self.projectiles.remove(proj)
            
            # Update explosions
            for exp in self.explosions[:]:
                if not exp.update(dt):
                    self.explosions.remove(exp)
            
            # Update clouds
            for cloud in self.clouds:
                cloud.update(dt)
            
            # Collision detection
            self.check_collisions()
            
            # Check game over
            if not self.player.alive and not self.god_mode:
                if self.current_mission:
                    self.state = GameState.MISSION_FAILED
                else:
                    self.state = GameState.GAME_OVER
        
        elif self.state == GameState.MENU:
            # Rotate camera in menu
            pass
    
    def check_collisions(self):
        # Projectile vs Enemy
        for proj in self.projectiles[:]:
            if not proj.alive or proj.owner != "player":
                continue
            
            for enemy in self.enemies:
                if not enemy.alive:
                    continue
                
                if proj.position.distance_to(enemy.position) < enemy.size:
                    proj.alive = False
                    self.shots_hit += 1
                    
                    if enemy.take_damage(proj.damage):
                        # Enemy destroyed
                        self.explosions.append(Explosion(enemy.position))
                        
                        # Track mission kills
                        if self.current_mission:
                            enemy_type = enemy.type
                            self.mission_kills[enemy_type] = self.mission_kills.get(enemy_type, 0) + 1
                            
                            # Check elimination mission completion
                            if self.current_mission.type == MissionType.ELIMINATION:
                                if "target_type" in self.current_mission.objectives:
                                    target_type = self.current_mission.objectives["target_type"]
                                    target_count = self.current_mission.objectives["target_count"]
                                    if self.mission_kills.get(target_type, 0) >= target_count:
                                        self.state = GameState.MISSION_COMPLETE
                                        self.current_mission.completed = True
                                        if self.current_mission.id < len(MISSIONS) - 1:
                                            MISSIONS[self.current_mission.id + 1].unlocked = True
                                elif "targets" in self.current_mission.objectives:
                                    # Check if all target types are eliminated
                                    all_complete = True
                                    for etype, count in self.current_mission.objectives["targets"].items():
                                        if self.mission_kills.get(etype, 0) < count:
                                            all_complete = False
                                            break
                                    if all_complete:
                                        self.state = GameState.MISSION_COMPLETE
                                        self.current_mission.completed = True
                                        if self.current_mission.id < len(MISSIONS) - 1:
                                            MISSIONS[self.current_mission.id + 1].unlocked = True
                        
                        # Score calculation
                        base_score = {"scout": 100, "jet": 200, "bomber": 300}[enemy.type]
                        combo_bonus = 1 + (self.combo * 0.5)
                        missile_bonus = 2 if proj.is_missile else 1
                        
                        points = int(base_score * combo_bonus * missile_bonus)
                        self.score += points
                        
                        # Combo system
                        self.combo += 1
                        self.combo_timer = 3.0
                    
                    break
        
        # Projectile vs Player
        if not self.god_mode:
            for proj in self.projectiles[:]:
                if not proj.alive or proj.owner != "enemy":
                    continue
                
                if proj.position.distance_to(self.player.position) < 15:
                    proj.alive = False
                    self.player.take_damage(proj.damage)
                    
                    if not self.player.alive:
                        self.explosions.append(Explosion(self.player.position))
        
        # Projectile vs Friendly Aircraft (escort mission)
        if self.friendly_aircraft and self.friendly_aircraft.alive:
            for proj in self.projectiles[:]:
                if not proj.alive or proj.owner != "enemy":
                    continue
                
                if proj.position.distance_to(self.friendly_aircraft.position) < 10:
                    proj.alive = False
                    self.friendly_aircraft.take_damage(proj.damage)
                    if not self.friendly_aircraft.alive:
                        self.explosions.append(Explosion(self.friendly_aircraft.position))
        
        # Enemy vs Player collision
        if not self.god_mode:
            for enemy in self.enemies:
                if enemy.alive and self.player.alive:
                    if enemy.position.distance_to(self.player.position) < enemy.size + 10:
                        enemy.take_damage(enemy.max_health)
                        self.player.take_damage(30)
                        self.explosions.append(Explosion(enemy.position))


    
    def render(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        
        if self.state == GameState.MENU:
            self.render_menu()
        elif self.state == GameState.MISSION_SELECT:
            self.render_mission_select()
        elif self.state == GameState.MISSION_BRIEFING:
            self.render_mission_briefing()
        elif self.state == GameState.PLAYING or self.state == GameState.PAUSED:
            self.render_game()
            if self.state == GameState.PAUSED:
                self.render_pause_overlay()
        elif self.state == GameState.MISSION_COMPLETE:
            self.render_game()
            self.render_mission_complete()
        elif self.state == GameState.MISSION_FAILED:
            self.render_game()
            self.render_mission_failed()
        elif self.state == GameState.GAME_OVER:
            self.render_game()
            self.render_game_over()
        
        glutSwapBuffers()
    
    def render_game(self):
        # Set up 3D perspective
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(60, WIN_W / WIN_H, 1, 2000)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        
        # Apply camera
        self.camera.apply(self.player)
        
        # Enable depth test and blending
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        
        # Render sky gradient
        self.render_sky()
        
        # Render clouds
        for cloud in self.clouds:
            cloud.render()
        
        # Render world boundaries (invisible but helpful for debugging)
        # self.render_boundaries()
        
        # Render player
        if self.player.alive:
            self.player.render()
        
        # Render enemies
        for enemy in self.enemies:
            enemy.render()
        
        # Render mission-specific objects
        if self.friendly_aircraft:
            self.friendly_aircraft.render()
        
        if self.defense_base:
            self.defense_base.render()
        
        # Render projectiles
        for proj in self.projectiles:
            proj.render()
        
        # Render explosions
        for exp in self.explosions:
            exp.render()
        
        glDisable(GL_DEPTH_TEST)
        
        # Render HUD
        self.render_hud()
        
        # Render Cockpit Overlay if in Cockpit mode
        if self.camera.mode == CameraMode.COCKPIT:
            self.render_cockpit()
    
    def render_sky(self):
        """Render sky gradient background"""
        glDisable(GL_DEPTH_TEST)
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        glOrtho(-1, 1, -1, 1, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()
        
        glBegin(GL_QUADS)
        # Top (lighter blue)
        glColor3f(0.4, 0.6, 0.9)
        glVertex2f(-1, 1)
        glVertex2f(1, 1)
        # Bottom (darker blue)
        glColor3f(0.2, 0.3, 0.5)
        glVertex2f(1, -1)
        glVertex2f(-1, -1)
        glEnd()
        
        glPopMatrix()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        glEnable(GL_DEPTH_TEST)
    
    def render_hud(self):
        """Render HUD elements"""
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        glOrtho(0, WIN_W, 0, WIN_H, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()
        
        # Health bar
        health_percent = self.player.health / self.player.max_health
        bar_width = 300
        bar_height = 20
        bar_x = 20
        bar_y = WIN_H - 40
        
        # Background
        glColor3f(0.2, 0.2, 0.2)
        glBegin(GL_QUADS)
        glVertex2f(bar_x, bar_y)
        glVertex2f(bar_x + bar_width, bar_y)
        glVertex2f(bar_x + bar_width, bar_y + bar_height)
        glVertex2f(bar_x, bar_y + bar_height)
        glEnd()
        
        # Health
        if health_percent > 0.6:
            glColor3f(0, 1, 0)
        elif health_percent > 0.3:
            glColor3f(1, 1, 0)
        else:
            glColor3f(1, 0, 0)
        
        glBegin(GL_QUADS)
        glVertex2f(bar_x, bar_y)
        glVertex2f(bar_x + bar_width * health_percent, bar_y + bar_height)
        glVertex2f(bar_x, bar_y + bar_height)
        glEnd()
        
        # Draw text info
        self.render_text(f"SCORE: {self.score}", 20, WIN_H - 70)
        self.render_text(f"ALT: {int(self.player.position.y)}", 20, WIN_H - 90)
        self.render_text(f"SPD: {int(300 + self.player.velocity.length() * 5)}", 20, WIN_H - 110)
        
        # Weapon status
        self.render_text(f"MISSILES: {self.player.missiles}", 20, WIN_H - 140)
        
        if self.current_mission:
             self.render_text(f"MISSION: {self.current_mission.name}", WIN_W - 250, WIN_H - 40)
             
             # Mission specific objectives
             if self.current_mission.type == MissionType.DEFENSE:
                 if self.defense_base:
                      self.render_text(f"BREACHES: {self.defense_base.breaches}/{self.current_mission.objectives['max_breaches']}", WIN_W - 250, WIN_H - 60)
             elif self.current_mission.type == MissionType.ELIMINATION:
                 if "target_type" in self.current_mission.objectives:
                     ttype = self.current_mission.objectives["target_type"]
                     tcount = self.current_mission.objectives["target_count"]
                     killed = self.mission_kills.get(ttype, 0)
                     self.render_text(f"TARGETS: {killed}/{tcount}", WIN_W - 250, WIN_H - 60)

        # Crosshair (only if not in cockpit mode, cockpit has its own)
        # Crosshair (only if not in cockpit mode, cockpit has its own)
        if self.camera.mode != CameraMode.COCKPIT:
             self.render_crosshair()
             
        glMatrixMode(GL_MODELVIEW)
        glPopMatrix()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
    
    def render_cockpit(self):
        """Render cockpit interior overlay"""
        glDisable(GL_DEPTH_TEST)
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        glOrtho(0, WIN_W, 0, WIN_H, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()
        
        # Cockpit Color (Dark Grey)
        glColor3f(0.15, 0.15, 0.18)
        
        # Bottom Dashboard
        glBegin(GL_QUADS)
        glVertex2f(0, 0)
        glVertex2f(WIN_W, 0)
        glVertex2f(WIN_W, WIN_H * 0.35) # Dashboard height
        glVertex2f(0, WIN_H * 0.35)
        glEnd()
        
        # Frame sides (simulate canopy)
        glColor3f(0.1, 0.1, 0.12)
        glBegin(GL_QUADS)
        # Left pillar
        glVertex2f(0, WIN_H * 0.35)
        glVertex2f(WIN_W * 0.15, WIN_H * 0.35)
        glVertex2f(WIN_W * 0.05, WIN_H)
        glVertex2f(0, WIN_H)
        
        # Right pillar
        glVertex2f(WIN_W, WIN_H * 0.35)
        glVertex2f(WIN_W * 0.85, WIN_H * 0.35)
        glVertex2f(WIN_W * 0.95, WIN_H)
        glVertex2f(WIN_W, WIN_H)
        
        # Top frame
        glVertex2f(0, WIN_H * 0.95)
        glVertex2f(WIN_W, WIN_H * 0.95)
        glVertex2f(WIN_W, WIN_H)
        glVertex2f(0, WIN_H)
        glEnd()
        
        # Instruments
        center_x = WIN_W / 2
        dash_y = WIN_H * 0.2
        
        # Radar Screen (Center)
        glColor3f(0.0, 0.2, 0.0)
        glBegin(GL_QUADS)
        glVertex2f(center_x - 60, dash_y - 60)
        glVertex2f(center_x + 60, dash_y - 60)
        glVertex2f(center_x + 60, dash_y + 60)
        glVertex2f(center_x - 60, dash_y + 60)
        glEnd()
        
        # Radar Outline
        glColor3f(0.3, 0.3, 0.3)
        glLineWidth(2)
        glBegin(GL_LINE_LOOP)
        glVertex2f(center_x - 60, dash_y - 60)
        glVertex2f(center_x + 60, dash_y - 60)
        glVertex2f(center_x + 60, dash_y + 60)
        glVertex2f(center_x - 60, dash_y + 60)
        glEnd()
        
        # Radar blips
        # Draw player center
        glColor3f(0.0, 1.0, 0.0)
        glBegin(GL_POINTS)
        glVertex2f(center_x, dash_y)
        glEnd()
        
        # Draw simplified enemies on this mini-radar
        # We need to project 3D relative pos to 2D
        glPointSize(3)
        glBegin(GL_POINTS)
        for enemy in self.enemies:
            if enemy.alive:
                # Relative pos
                rel_x = enemy.position.x - self.player.position.x
                rel_z = enemy.position.z - self.player.position.z
                
                # Simple rotation to match player heading
                rad = math.radians(self.player.rotation)
                rot_x = rel_x * math.cos(-rad) - rel_z * math.sin(-rad)
                rot_z = rel_x * math.sin(-rad) + rel_z * math.cos(-rad)
                
                # Scale down for radar
                radar_scale = 0.05
                r_x = center_x + rot_x * radar_scale
                r_y = dash_y - rot_z * radar_scale # Z is forward/back, maps to Y on screen
                
                # Clamp to radar screen
                if abs(r_x - center_x) < 55 and abs(r_y - dash_y) < 55:
                     glColor3f(1.0, 0.0, 0.0)
                     glVertex2f(r_x, r_y)
        glEnd()
        glPointSize(1)
        
        # HUD / Glass info (Green text on "glass")
        self.render_text("HUD ACTIVE", center_x - 30, WIN_H * 0.6, (0, 1, 0))
        
        # Artificial Horizon Line (Simplified)
        pitch_offset = self.player.pitch * 2
        glColor3f(0.5, 1.0, 0.0)
        glLineWidth(1)
        glBegin(GL_LINES)
        glVertex2f(center_x - 100, WIN_H * 0.5 + pitch_offset)
        glVertex2f(center_x + 100, WIN_H * 0.5 + pitch_offset)
        
        # Vertical markers on horizon
        glVertex2f(center_x - 100, WIN_H * 0.5 + pitch_offset - 5)
        glVertex2f(center_x - 100, WIN_H * 0.5 + pitch_offset + 5)
        glVertex2f(center_x + 100, WIN_H * 0.5 + pitch_offset - 5)
        glVertex2f(center_x + 100, WIN_H * 0.5 + pitch_offset + 5)
        glEnd()
        
        # Crosshair projected
        glColor3f(0.0, 1.0, 0.0)
        glBegin(GL_LINES)
        glVertex2f(center_x - 10, WIN_H * 0.5)
        glVertex2f(center_x + 10, WIN_H * 0.5)
        glVertex2f(center_x, WIN_H * 0.5 - 10)
        glVertex2f(center_x, WIN_H * 0.5 + 10)
        glEnd()
        
        glPopMatrix()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        glEnable(GL_DEPTH_TEST)
        
        # Score
        self.render_text(f"SCORE: {self.score}", WIN_W - 250, WIN_H - 40)
        
        # Combo
        if self.combo > 1:
            self.render_text(f"COMBO x{self.combo}", WIN_W - 250, WIN_H - 70, (1, 0.8, 0))
        
        # Ammo
        self.render_text(f"MISSILES: {self.player.missiles}", 20, 60)
        
        # Accuracy
        if self.shots_fired > 0:
            accuracy = int((self.shots_hit / self.shots_fired) * 100)
            self.render_text(f"ACCURACY: {accuracy}%", 20, 30)
        
        # Minimap radar
        self.render_radar()
        
        # 2D Crosshair (aiming reticle)
        self.render_crosshair()
        
        # Debug info
        if self.god_mode:
            self.render_text("GOD MODE", WIN_W // 2 - 50, WIN_H - 40, (1, 1, 0))
    
    def render_radar(self):
        """Render minimap radar"""
        radar_size = 150
        radar_x = WIN_W - radar_size - 20
        radar_y = 20
        
        # Background
        glColor4f(0, 0, 0, 0.5)
        glBegin(GL_QUADS)
        glVertex2f(radar_x, radar_y)
        glVertex2f(radar_x + radar_size, radar_y)
        glVertex2f(radar_x + radar_size, radar_y + radar_size)
        glVertex2f(radar_x, radar_y + radar_size)
        glEnd()
        
        # Border
        glColor3f(0, 1, 0)
        glBegin(GL_LINE_LOOP)
        glVertex2f(radar_x, radar_y)
        glVertex2f(radar_x + radar_size, radar_y)
        glVertex2f(radar_x + radar_size, radar_y + radar_size)
        glVertex2f(radar_x, radar_y + radar_size)
        glEnd()
        
        # Player (center)
        center_x = radar_x + radar_size / 2
        center_y = radar_y + radar_size / 2
        glColor3f(0, 1, 0)
        glPointSize(5)
        glBegin(GL_POINTS)
        glVertex2f(center_x, center_y)
        glEnd()
        
        # Enemies
        scale = radar_size / (WORLD_SIZE * 2)
        for enemy in self.enemies:
            if enemy.alive:
                rel_x = (enemy.position.x - self.player.position.x) * scale
                rel_z = (enemy.position.z - self.player.position.z) * scale
                
                ex = center_x + rel_x
                ey = center_y - rel_z  # Flip Z for screen coords
                
                # Only show if in radar range
                if (radar_x < ex < radar_x + radar_size and 
                    radar_y < ey < radar_y + radar_size):
                    glColor3f(1, 0, 0)
                    glBegin(GL_POINTS)
                    glVertex2f(ex, ey)
                    glEnd()
        
        glPointSize(1)
    
    def render_crosshair(self):
        """Render 2D aiming crosshair in center of screen"""
        center_x = WIN_W / 2
        center_y = WIN_H / 2 + 80  # Offset upward to represent aiming above plane
        size = 20
        gap = 5
        thickness = 2
        
        glColor3f(0, 1, 0)  # Green crosshair
        glLineWidth(thickness)
        
        # Draw + sign
        glBegin(GL_LINES)
        # Horizontal line (left)
        glVertex2f(center_x - size, center_y)
        glVertex2f(center_x - gap, center_y)
        # Horizontal line (right)
        glVertex2f(center_x + gap, center_y)
        glVertex2f(center_x + size, center_y)
        # Vertical line (top)
        glVertex2f(center_x, center_y + gap)
        glVertex2f(center_x, center_y + size)
        # Vertical line (bottom)
        glVertex2f(center_x, center_y - size)
        glVertex2f(center_x, center_y - gap)
        glEnd()
        
        # Center dot
        glPointSize(4)
        glBegin(GL_POINTS)
        glVertex2f(center_x, center_y)
        glEnd()
        glPointSize(1)
        
        glLineWidth(1)

    def render_text(self, text, x, y, color=(1, 1, 1)):
        """Simple text rendering using GLUT"""
        glColor3f(*color)
        glRasterPos2f(x, y)
        for char in text:
            glutBitmapCharacter(GLUT_BITMAP_HELVETICA_18, ord(char))
    
    def render_menu(self):
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0, WIN_W, 0, WIN_H, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        
        self.render_text("SKYSTRIKE", WIN_W // 2 - 80, WIN_H // 2 + 100, (0.2, 0.8, 1.0))
        self.render_text("Aerial Combat Simulation", WIN_W // 2 - 120, WIN_H // 2 + 60)
        self.render_text("Press SPACE to Start", WIN_W // 2 - 100, WIN_H // 2)
        self.render_text("Controls:", WIN_W // 2 - 200, WIN_H // 2 - 60)
        self.render_text("  W/S - Pitch Up/Down", WIN_W // 2 - 200, WIN_H // 2 - 90)
        self.render_text("  A/D - Turn Left/Right", WIN_W // 2 - 200, WIN_H // 2 - 120)
        self.render_text("  SPACE/SHIFT - Altitude", WIN_W // 2 - 200, WIN_H // 2 - 150)
        self.render_text("  Left Click - Machine Gun", WIN_W // 2 - 200, WIN_H // 2 - 180)
        self.render_text("  Right Click - Missile", WIN_W // 2 - 200, WIN_H // 2 - 210)
        self.render_text("  C - Change Camera", WIN_W // 2 - 200, WIN_H // 2 - 240)
        self.render_text("  ESC - Pause", WIN_W // 2 - 200, WIN_H // 2 - 270)
    
    def render_pause_overlay(self):
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0, WIN_W, 0, WIN_H, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        
        # Semi-transparent overlay
        glColor4f(0, 0, 0, 0.5)
        glBegin(GL_QUADS)
        glVertex2f(0, 0)
        glVertex2f(WIN_W, 0)
        glVertex2f(WIN_W, WIN_H)
        glVertex2f(0, WIN_H)
        glEnd()
        
        self.render_text("PAUSED", WIN_W // 2 - 50, WIN_H // 2, (1, 1, 0))
        self.render_text("Press ESC to Resume", WIN_W // 2 - 100, WIN_H // 2 - 40)
    
    def render_game_over(self):
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0, WIN_W, 0, WIN_H, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        
        # Semi-transparent overlay
        glColor4f(0, 0, 0, 0.7)
        glBegin(GL_QUADS)
        glVertex2f(0, 0)
        glVertex2f(WIN_W, 0)
        glVertex2f(WIN_W, WIN_H)
        glVertex2f(0, WIN_H)
        glEnd()
        
        self.render_text("GAME OVER", WIN_W // 2 - 70, WIN_H // 2 + 50, (1, 0, 0))
        self.render_text(f"Final Score: {self.score}", WIN_W // 2 - 80, WIN_H // 2)
        
        if self.shots_fired > 0:
            accuracy = int((self.shots_hit / self.shots_fired) * 100)
            self.render_text(f"Accuracy: {accuracy}%", WIN_W // 2 - 70, WIN_H // 2 - 40)
        
        self.render_text("Press R to Restart", WIN_W // 2 - 90, WIN_H // 2 - 100)
        self.render_text("Press Q to Quit", WIN_W // 2 - 70, WIN_H // 2 - 130)






game = None

def display():
    game.render()

def idle():
    current_time = time.time()
    dt = current_time - game.last_time
    game.last_time = current_time
    
    # Handle continuous machine gun firing
    if game.state == GameState.PLAYING and game.mouse_left:
        proj = game.player.fire_machine_gun()
        if proj:
            game.projectiles.append(proj)
            game.shots_fired += 1
    
    game.update(dt)
    glutPostRedisplay()

def reshape(w, h):
    glViewport(0, 0, w, h)



def keyboard(key, x, y):
    k = key.decode('utf-8').lower()
    
    if game.state == GameState.MENU:
        if k == ' ':
            game.reset()
    
    elif game.state == GameState.PLAYING:
        if k == '\x1b':  # ESC
            game.state = GameState.PAUSED
        elif k == 'w':
            game.player.input_up = True
        elif k == 's':
            game.player.input_down = True
        elif k == 'a':
            game.player.input_left = True
        elif k == 'd':
            game.player.input_right = True
        elif k == ' ':
            game.player.input_up = True
        elif k == '\t':  # TAB key for going down
            game.player.input_down = True
        elif k == 'c':
            game.camera.cycle()
        # Debug keys
        elif k == 'g':
            game.god_mode = not game.god_mode
            print(f"God mode: {game.god_mode}")
    
    elif game.state == GameState.PAUSED:
        if k == '\x1b':  # ESC
            game.state = GameState.PLAYING
    
    elif game.state == GameState.GAME_OVER:
        if k == 'r':
            game.reset()
        elif k == 'q':
            sys.exit(0)

def keyboard_up(key, x, y):
    k = key.decode('utf-8').lower()
    
    if k == 'w':
        game.player.input_up = False
    elif k == 's':
        game.player.input_down = False
    elif k == 'a':
        game.player.input_left = False
    elif k == 'd':
        game.player.input_right = False
    elif k == ' ':
        game.player.input_up = False
    elif k == '\t':  # TAB key release
        game.player.input_down = False

def special(key, x, y):
    pass

def special_up(key, x, y):
    pass

def mouse(button, state, x, y):
    if game.state == GameState.PLAYING:
        if button == GLUT_LEFT_BUTTON:
            if state == GLUT_DOWN:
                game.mouse_left = True
            else:
                game.mouse_left = False
        
        elif button == GLUT_RIGHT_BUTTON:
            if state == GLUT_DOWN:
                game.mouse_right = True
                # Fire missile
                proj = game.player.fire_missile()
                if proj:
                    game.projectiles.append(proj)
                    game.shots_fired += 1
            else:
                game.mouse_right = False

def main():
    global game
    
    glutInit(sys.argv)
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGBA | GLUT_DEPTH)
    glutInitWindowSize(WIN_W, WIN_H)
    glutInitWindowPosition(100, 100)
    glutCreateWindow(GAME_TITLE)
    
    # OpenGL settings
    glClearColor(0.2, 0.3, 0.5, 1.0)
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glPointSize(3)
    
    # Initialize game
    game = SkyStrike()
    
    # Register callbacks
    glutDisplayFunc(display)
    glutIdleFunc(idle)
    glutReshapeFunc(reshape)
    glutKeyboardFunc(keyboard)
    glutKeyboardUpFunc(keyboard_up)
    glutSpecialFunc(special)
    glutSpecialUpFunc(special_up)
    glutMouseFunc(mouse)
  
    
    print("SkyStrike - Aerial Combat Simulation")
    print("=" * 50)
    print("Controls:")
    print("  W/S - Pitch Up/Down")
    print("  A/D - Turn Left/Right")
    print("  SPACE/SHIFT - Altitude Up/Down")
    print("  Left Click - Machine Gun")
    print("  Right Click - Missile")
    print("  C - Change Camera Mode")
    print("  ESC - Pause/Resume")
    print("  G - Toggle God Mode (debug)")
    print("=" * 50)
    
    glutMainLoop()

if __name__ == "__main__":
    main()
