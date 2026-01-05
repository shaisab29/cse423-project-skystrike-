"""
SkyStrike - 3D Aerial Combat Simulation
A comprehensive aerial combat game featuring intelligent AI, multi-camera systems,
advanced weapon mechanics, and progressive difficulty.
"""

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
    glutMotionFunc(motion)
    glutPassiveMotionFunc(passive_motion)
    
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
