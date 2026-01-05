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
