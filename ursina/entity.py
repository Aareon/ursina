import sys
import inspect
import importlib
import random
import glob
from pathlib import Path
from panda3d.core import PandaNode
from panda3d.core import NodePath
from panda3d.core import GeomNode
from panda3d.core import GeomVertexReader
from panda3d.core import Vec3, Vec4
from panda3d.core import Point3
from panda3d.core import TransparencyAttrib
from panda3d.core import Shader
from panda3d.core import TextureStage, TexGenAttrib, GeomVertexReader

from ursina.texture import Texture
from panda3d.core import MovieTexture
from panda3d.core import TextureStage
from panda3d.core import CullFaceAttrib
from ursina import application
from ursina.collider import *
from ursina.mesh import Mesh
from os import path
from ursina.sequence import Sequence, Func, Wait
from ursina.ursinamath import lerp
from ursina import curve
from ursina.useful import *
from ursina.mesh_importer import load_model
from ursina.texture_importer import load_texture

from ursina import color
try:
    from ursina import scene
except:
    pass



class Entity(NodePath):


    def __init__(self, **kwargs):
        super().__init__(self.__class__.__name__)

        self.name = camel_to_snake(self.type)
        self.enabled = True
        self.visible = True
        self.ignore = False     # if True, will not try to run code or be added to scene.entities

        self.parent = scene
        scene.entities.append(self)

        self.eternal = False    # eternal entities does not get destroyed on scene.clear()
        self.ignore_paused = False
        self.model = None
        self.color = color.white
        self.texture = None     # tries to set to camel_to_snake(self.type)
        self.reflection_map = scene.reflection_map
        self.reflectivity = 0

        self.texture = camel_to_snake(self.type)
        self.render_queue = 0
        self.double_sided = False

        self.collision = False
        self.collider = None
        self.scripts = list()
        self.animations = list()
        self.hovered = False
        #
        self.origin = Vec3(0,0,0)
        self.position = Vec3(0,0,0) # can also set self.x, self.y, self.z
        self.rotation = Vec3(0,0,0) # can also set self.rotation_x, self.rotation_y, self.rotation_z
        self.scale = Vec3(1,1,1)    # can also set self.scale_x, self.scale_y, self.scale_z

        self.line_definition = None
        if application.trace_entity_definition:
            from inspect import getframeinfo, stack
            caller = getframeinfo(stack()[1][0])
            self.line_definition = f'{Path(caller.filename).name} ->  {caller.lineno} -> {caller.code_context}'

        for key, value in kwargs.items():
            setattr(self, key, value)


    def __setattr__(self, name, value):

        if name == 'enabled':
            try:
                # try calling on_enable() on classes inheriting from Entity
                if value == True:
                    self.on_enable()
                else:
                    self.on_disable()
            except:
                pass

            if value == True:
                if not self.is_singleton():
                    self.unstash()
            else:
                if not self.is_singleton():
                    self.stash()


        if name == 'world_parent':
            self.reparent_to(value)

        if name == 'model':
            if value is None:
                if hasattr(self, 'model') and self.model:
                    self.model.removeNode()
                    # print('removed model')
                object.__setattr__(self, name, value)
                return None

            if isinstance(value, NodePath): # pass procedural model
                if self.model is not None and value != self.model:
                    self.model.removeNode()
                object.__setattr__(self, name, value)

            elif isinstance(value, str): # pass model asset name
                m = load_model(value, application.asset_folder)
                if not m:
                    m = load_model(value, application.internal_models_folder)
                if m:
                    if self.model is not None:
                        self.model.removeNode()
                    object.__setattr__(self, name, m)
                    if isinstance(m, Mesh):
                        m.recipe = value # needed when duplicating entity
                    # print('loaded model successively')
                else:
                    print('error loading model:', value)

            if self.model:
                self.model.reparentTo(self)
                self.model.setTransparency(TransparencyAttrib.MAlpha)
                setattr(self, 'color', self.color) # reapply color after changing model
                self._vert_cache = None
                if isinstance(value, Mesh):
                    if hasattr(value, 'on_assign'):
                        value.on_assign(assigned_to=self)
                return
            else:
                print('missing model:', value)

        if name == 'color' and value is not None:
            if not isinstance(value, Vec4):
                value = Vec4(value[0], value[1], value[2], value[3])

            if self.model:
                self.model.setColorScale(value)
                object.__setattr__(self, name, value)


        if name == 'texture_scale':
            if self.model and self.texture:
                self.model.setTexScale(TextureStage.getDefault(), value[0], value[1])

        if name == 'texture_offset':
            if self.model and self.texture:
                self.model.setTexOffset(TextureStage.getDefault(), value[0], value[1])
                self.texture = self.texture

        if name == 'position':
            # automatically add position instead of extending the tuple
            new_value = Vec3()

            if len(value) % 2 == 0:
                for i in range(0, len(value), 2):
                    new_value.add_x(value[i])
                    new_value.add_y(value[i+1])
                new_value.add_z(self.getY())

            if len(value) % 3 == 0:
                for i in range(0, len(value), 3):
                    new_value.add_x(value[i])
                    new_value.add_y(value[i+1])
                    new_value.add_z(value[i+2])

            try:
                self.setPos(new_value[0], new_value[2], new_value[1])
            except:
                pass    # can't set position

        if name == 'x': self.setX(value)
        if name == 'y': self.setZ(value)
        if name == 'z': self.setY(value)

        if name == 'origin' and self.model:
            new_value = Vec3()

            if len(value) % 2 == 0:
                for i in range(0, len(value), 2):
                    new_value.add_x(value[i])
                    new_value.add_y(value[i+1])
                new_value.add_z(self.model.getY())

            if len(value) % 3 == 0:
                for i in range(0, len(value), 3):
                    new_value.add_x(value[i])
                    new_value.add_y(value[i+1])
                    new_value.add_z(value[i+2])

            self.model.setPos(-new_value[0], -new_value[2], -new_value[1])
            object.__setattr__(self, name, new_value)
            return

        if name == 'rotation':
            new_value = Vec3()

            if len(value) % 2 == 0:
                for i in range(0, len(value), 2):
                    new_value.add_x(value[i])
                    new_value.add_y(value[i+1])
                new_value.add_z(self.getR())

            if len(value) % 3 == 0:
                for i in range(0, len(value), 3):
                    new_value.add_x(value[i])
                    new_value.add_y(value[i+1])
                    new_value.add_z(value[i+2])

            self.setHpr(Vec3(-new_value[1], -new_value[0], new_value[2]))

        if name == 'rotation_x': self.setP(-value)
        if name == 'rotation_y': self.setH(-value)
        if name == 'rotation_z': self.setR(value)

        if name == 'scale':
            if isinstance(value, (int, float, complex)):
                value = (value, value, value)

            new_value = Vec3()

            if len(value) % 2 == 0:
                for i in range(0, len(value), 2):
                    new_value.add_x(value[i])
                    new_value.add_y(value[i+1])
                new_value.add_z(self.getSy())

            if len(value) % 3 == 0:
                for i in range(0, len(value), 3):
                    new_value.add_x(value[i])
                    new_value.add_y(value[i+1])
                    new_value.add_z(value[i+2])

            for e in new_value:
                if e == 0:
                    e = .001

            self.setScale(new_value[0], new_value[2], new_value[1])

        if name == 'scale_x':
            self.set_scale(value, self.scale_z, self.scale_y)

        if name == 'scale_y':
            self.set_scale(self.scale_x, self.scale_z, value)

        if name == 'scale_z':
            self.set_scale(self.scale_x, value, self.scale_y)



        if name == 'collider':
            # destroy excisting collider
            if hasattr(self, 'collider') and self.collider:
                self.collider.remove()

            if value == None or isinstance(value, Collider):
                self.collision = not value == None
                object.__setattr__(self, name, value)

            elif value == 'box':
                if self.model:
                    collider = BoxCollider(
                        entity = self,
                        center = -self.origin,
                        size = self.model_bounds
                        )
                else:
                    collider = BoxCollider(entity=self)

                self.collision = True
                object.__setattr__(self, name, collider)
                return

            elif value == 'sphere':
                collider = SphereCollider(entity=self)
                self.collision = True
                object.__setattr__(self, name, collider)
                return

            elif value == 'mesh' and self.model:
                collider = MeshCollider(entity=self, center=-self.origin)
                self.collision = True
                object.__setattr__(self, name, collider)
                return

            else:
                print('collider error:', value, 'is not a collider')

        if name == 'collision' and hasattr(self, 'collider') and self.collider:
            if value:
                self.collider.node_path.unstash()
            else:
                self.collider.node_path.stash()

            object.__setattr__(self, name, value)
            return


        if name == 'render_queue':
            if self.model:
                self.model.setBin('fixed', value)

        if name == 'double_sided':
            self.setTwoSided(value)

        try:
            super().__setattr__(name, value)
        except:
            pass
            # print('failed to sett attribiute:', name)


    @property
    def parent(self):
        try:
            return self._parent
        except:
            return None

    @parent.setter
    def parent(self, value):
        self._parent = value
        if value is None:
            destroy(self)
        else:
            try:
                self.reparentTo(value)
            except:
                print('invalid parent:', value)

    @property
    def type(self):
        return self.__class__.__name__

    @property
    def types(self):
        return [c.__name__ for c in inspect.getmro(self.__class__)]


    @property
    def visible(self):
        return self._visible

    @visible.setter
    def visible(self, value):
        self._visible = value
        if value:
            self.show()
        else:
            self.hide()

    @property
    def origin_x(self):
        return self.origin[0]
    @origin_x.setter
    def origin_x(self, value):
        self.origin = (value, self.origin_y, self.origin_z)

    @property
    def origin_y(self):
        return self.origin[1]
    @origin_y.setter
    def origin_y(self, value):
        self.origin = (self.origin_x, value, self.origin_z)

    @property
    def origin_z(self):
        return self.origin[2]
    @origin_z.setter
    def origin_z(self, value):
        self.origin = (self.origin_x, self.origin_y, value)

    @property
    def world_position(self):
        return self.get_position(render)

    @world_position.setter
    def world_position(self, value):
        value = Vec3(value[0], value[2], value[1])
        self.setPos(render, value)

    @property
    def world_x(self):
        return self.getX(render)
    @property
    def world_y(self):
        return self.getZ(render)
    @property
    def world_z(self):
        return self.getY(render)

    @world_x.setter
    def world_x(self, value):
        self.setX(render, value)
    @world_y.setter
    def world_y(self, value):
        self.setZ(render, value)
    @world_z.setter
    def world_z(self, value):
        self.setY(render, value)

    @property
    def position(self):
        return Vec3(self.getX(), self.getZ(), self.getY())
    @property
    def x(self):
        return self.getX()
    @property
    def y(self):
        return self.getZ()
    @property
    def z(self):
        return self.getY()

    @property
    def world_rotation(self):
        rotation = self.getHpr(base.render)
        return Vec3(-rotation[1], -rotation[0], rotation[2])
    @property
    def world_rotation_x(self):
        return -self.getP(base.render)
    @property
    def world_rotation_y(self):
        return -self.getH(base.render)
    @property
    def world_rotation_z(self):
        return self.getR(base.render)

    @property
    def rotation(self):
        rotation = self.getHpr()
        return Vec3(-rotation[1], -rotation[0], rotation[2])
    @property
    def rotation_x(self):
        return -self.getP()
    @property
    def rotation_y(self):
        return -self.getH()
    @property
    def rotation_z(self):
        return self.getR()


    @property
    def world_scale(self):
        scale = self.getScale(base.render)
        return Vec3(scale[0], scale[2], scale[1])
    @world_scale.setter
    def world_scale(self, value):
        if isinstance(value, (int, float, complex)):
            value = (value, value, value)

        self.setScale(base.render, Vec3(value[0], value[2], value[1]))

    @property
    def world_scale_x(self):
        return self.getScale(base.render)[0]
    @world_scale_x.setter
    def world_scale_x(self, value):
        self.setScale(base.render, Vec3(value, self.world_scale_z, self.world_scale_y))

    @property
    def world_scale_y(self):
        return self.getScale(base.render)[2]
    @world_scale_y.setter
    def world_scale_y(self, value):
        self.setScale(base.render, Vec3(self.world_scale_x, self.world_scale_z, value))

    @property
    def world_scale_z(self):
        return self.getScale(base.render)[1]
    @world_scale_z.setter
    def world_scale_z(self, value):
        self.setScale(base.render, Vec3(self.world_scale_x, value, self.world_scale_y))

    @property
    def scale(self):
        scale = self.getScale()
        return Vec3(scale[0], scale[2], scale[1])
    @property
    def scale_x(self):
        return self.getScale()[0]
    @property
    def scale_y(self):
        return self.getScale()[2]
    @property
    def scale_z(self):
        return self.getScale()[1]

    @property
    def forward(self):
        vec =  render.getRelativeVector(self, (0, 1, 0))
        return Vec3(vec[0], vec[2], vec[1])
    @property
    def back(self):
        return -self.forward
    @property
    def right(self):
        vec =  render.getRelativeVector(self, (1, 0, 0))
        return Vec3(vec[0], vec[2], vec[1])
    @property
    def left(self):
        return -self.right
    @property
    def up(self):
        vec = render.getRelativeVector(self, (0, 0, 1))
        return Vec3(vec[0], vec[2], vec[1])
    @property
    def down(self):
        return -self.up

    @property
    def shader(self):
        return self.getShader()

    @shader.setter
    def shader(self, value):
        try:
            self.setShader(Shader.load(f'{value}.sha', Shader.SL_Cg))
        except:
            self.setShader(Shader.load(Shader.SL_GLSL, vertex=f'{value}.vert', fragment=f'{value}.frag'))

    @property
    def texture(self):
        if not hasattr(self, '_texture'):
            return None
        return self._texture

    @texture.setter
    def texture(self, value):
        if not self.model:
            return

        if value.__class__ is Texture:
            texture = value

        elif isinstance(value, str):
            texture = load_texture(value)
            print('loaded texture:', texture)

        if texture.__class__ is MovieTexture:
            self._texture = texture
            self.model.setTexture(texture)
            return

        try:
            self._texture = texture
            self.model.setTexture(texture._texture, 1)
            # print('set texture:', value)
        except:
            pass
            if value:
                print('no texture:', value)

        if value == None:
            self.model.set_texture_off(True)

    @property
    def alpha(self):
        return self.color[3]

    @alpha.setter
    def alpha(self, value):
        if value > 1:
            value = value / 255
        self.color = (self.color.h, self.color.s, self.color.v, value)

    @property
    def reflection_map(self):
        return self._reflection_map

    @reflection_map.setter
    def reflection_map(self, value):
        if value.__class__ is Texture:
            texture = value

        elif isinstance(value, str):
            texture = load_texture(value)

        self._reflection_map = texture


    @property
    def reflectivity(self):
        return self._reflectivity

    @reflectivity.setter
    def reflectivity(self, value):
        self._reflectivity = value

        if value == 0:
            self.texture = None

        if value > 0:
            # if self.reflection_map == None:
            #     self.reflection_map = scene.reflection_map
            #
            # if not self.reflection_map:
            #     print('error setting reflectivity. no reflection map')
            #     return
            if not self.normals:
                self.model.generate_normals()

            # ts = TextureStage('env')
            # ts.setMode(TextureStage.MAdd)
            # self.model.setTexGen(ts, TexGenAttrib.MEyeSphereMap)
            # print('---------------set reflectivity', self.reflection_map)
            # self.model.setTexture(ts, self.reflection_map)

            self.texture = self._reflection_map
            # print('set reflectivity')

    def generate_sphere_map(self, size=512, name=f'sphere_map_{len(scene.entities)}'):
        from ursina import camera
        _name = 'textures/' + name + '.jpg'
        org_pos = camera.position
        camera.position = self.position
        base.saveSphereMap(_name, size=size)
        camera.position = org_pos

        print('saved sphere map:', name)
        self.model.setTexGen(TextureStage.getDefault(), TexGenAttrib.MEyeSphereMap)
        self.reflection_map = name


    def generate_cube_map(self, size=512, name=f'cube_map_{len(scene.entities)}'):
        from ursina import camera
        _name = 'textures/' + name
        org_pos = camera.position
        camera.position = self.position
        base.saveCubeMap(_name+'.jpg', size=size)
        camera.position = org_pos

        print('saved cube map:', name + '.jpg')
        self.model.setTexGen(TextureStage.getDefault(), TexGenAttrib.MWorldCubeMap)
        self.reflection_map = _name + '#.jpg'
        self.model.setTexture(loader.loadCubeMap(_name + '#.jpg'), 1)


    @property
    def model_bounds(self):
        if self.model:
            bounds = self.model.getTightBounds()
            bounds = Vec3(
                Vec3(bounds[1][0], bounds[1][2], bounds[1][1])  # max point
                - Vec3(bounds[0][0], bounds[0][2], bounds[0][1])    # min point
                )
            return bounds
        else:
            return (0,0,0)

    @property
    def bounds(self):
        return Vec3(
            self.model_bounds[0] * self.scale_x,
            self.model_bounds[1] * self.scale_y,
            self.model_bounds[2] * self.scale_z
            )

    @property
    def vertex_data(self):
        if self.model and not self._vert_cache:
            geomNodeCollection = self.model.findAllMatches('**/+GeomNode')
            geomNode = geomNodeCollection[0].node()
            self._vert_cache = geomNode.getGeom(0).getVertexData()

        return self._vert_cache

    @property
    def vertices(self):
        return get_vertices(relative_to=self)

    def get_vertices(self, relative_to=None):
        if relative_to == None:
            relative_to = self

        vertex_reader = GeomVertexReader(self.vertex_data, 'vertex')
        vertices = list()
        temp_entity = Entity(parent=self, ignore=True)

        while not vertex_reader.isAtEnd():
            v = vertex_reader.getData3f()
            v = Vec3(v[0], v[2], v[1])
            temp_entity.position = v
            vertices.append(temp_entity.get_position(relative_to))

        from ursina import destroy
        destroy(temp_entity)

        return vertices

    @property
    def normals(self):
        vertex_reader = GeomVertexReader(self.vertex_data, 'normal')
        vertices = list()
        while not vertex_reader.isAtEnd():
            v = vertex_reader.getData3f()
            v = Vec3(v[0], v[2], v[1])
            vertices.append(v)
        return vertices

    @property
    def uvs(self):
        vertex_reader = GeomVertexReader(self.vertex_data, 'texcoord')
        vertices = list()
        while not vertex_reader.isAtEnd():
            vertices.append([e for e in vertex_reader.getData2f()])
        return vertices

    @property
    def vertex_colors(self):
        try:
            vcol_reader = GeomVertexReader(self.model.findAllMatches('**/+GeomNode')[0].node().getGeom(0).getVertexData(), 'color')
            vcols = list()
            while not vcol_reader.isAtEnd():
                vcols.append([e for e in vcol_reader.getData4f()])
            return vcols
        except:
            print(f'{self.name}.model has no vertex colors')
            return None


    def reparent_to(self, entity):
        if entity is not None:
            self.wrtReparentTo(entity)

        self._parent = entity


    def get_position(self, relative_to=scene):
        pos = self.getPos(relative_to)
        return Vec3(pos[0], pos[2], pos[1])


    def add_script(self, name, path=None):
        # instance given
        if isinstance(name, object) and type(name) is not str:
            name.entity = self
            name.enabled = True
            setattr(self, camel_to_snake(name.__class__.__name__), name)
            self.scripts.append(name)
            # print('added script:', camel_to_snake(name.__class__.__name__))
            return name

        # class name given
        if inspect.isclass(name):
            class_instance = name()
            class_instance.entity = self
            class_instance.enabled = True
            self.scripts.append(class_instance)
            # print('added script:', name)
            return class_instance

        # module name given as string
        folders = (application.asset_folder, application.internal_scripts_folder) # search order
        if path:
            folders = (path)

        for folder in folders:
            for filename in glob.iglob(str(folder) + '**/' + name + '.*', recursive=True):
                for ft in ('.py',):
                    if filename.endswith(ft):
                        module = importlib.machinery.SourceFileLoader(filename, name+ft).load_module()
                        class_names = inspect.getmembers(sys.modules[filename], inspect.isclass)
                        for cn in class_names:
                            if cn[1].__module__ == module.__name__:
                                class_name = cn[0]

                        class_ = getattr(module, class_name)
                        class_instance = class_()
                        class_instance.entity = self
                        class_instance.enabled = True

                        setattr(self, name, class_instance)
                        self.scripts.append(class_instance)
                        # print('added script:', name)
                        return class_instance

        print("couldn't find script:", name)
        return None


    def remove_script(self, module_name):
        for s in self.scripts:
            if s.__module__ == module_name:
                self.temp_script = s
                self.scripts.remove(s)
                self.__setattr__(module_name, None)
                print('removed:', module_name)


    def combine(self, analyze=False, auto_destroy=True):
        from ursina.scripts.combine import combine

        self.model = combine(self, analyze, auto_destroy)
        return self.model


    def flip_faces(self):
        if not hasattr(self, '_vertex_order'):
            self._vertex_order = True

        self._vertex_order = not self._vertex_order
        if self._vertex_order:
            self.setAttrib(CullFaceAttrib.make(CullFaceAttrib.MCullClockwise))
        else:
            self.setAttrib(CullFaceAttrib.make(CullFaceAttrib.MCullCounterClockwise))


    def look_at(self, target, axis='forward'):
        if isinstance(target, Entity):
            target = Vec3(target.world_position)
        super().look_at(render, Vec3(target[0], target[2], target[1]))

        self.rotation += {
        'forward' : (0,0,0),
        'back' :    (180,0,0),
        'right' :   (0,-90,0),
        'left' :    (0,90,0),
        'up' :      (90,0,0),
        'down' :    (-90,0,0),
        }[axis]

    def get_scripts_of_type(self, type):
        pass


    def has_ancestor(self, possible_ancestor):
        p = self
        if isinstance(possible_ancestor, Entity):
            # print('ENTITY')
            for i in range(100):
                if p.parent:
                    if p.parent == possible_ancestor:
                        return True
                        break
                    p = p.parent

        if isinstance(possible_ancestor, list) or isinstance(possible_ancestor, tuple):
            # print('LIST OR TUPLE')
            for e in possible_ancestor:
                for i in range(100):
                    if p.parent:
                        if p.parent == e:
                            return True
                            break
                        p = p.parent

        elif isinstance(possible_ancestor, str):
            print('CLASS NAME', possible_ancestor)
            for i in range(100):
                if p.parent:
                    if p.parent.__class__.__name__ == possible_ancestor:
                        return True
                        break
                    p = p.parent

        return False


    @property
    def children(self):
        return [e for e in scene.entities if e.parent == self]


    @property
    def attributes(self):
        return ('name', 'enabled', 'eternal', 'visible', 'parent',
            'origin', 'position', 'rotation', 'scale',
            'model', 'color', 'texture', 'texture_scale', 'texture_offset',

            # 'world_position', 'world_x', 'world_y', 'world_z',
            # 'world_rotation', 'world_rotation_x', 'world_rotation_y', 'world_rotation_z',
            # 'world_scale', 'world_scale_x', 'world_scale_y', 'world_scale_z',
            # 'x', 'y', 'z',
            # 'origin_x', 'origin_y', 'origin_z',
            # 'rotation_x', 'rotation_y', 'rotation_z',
            # 'scale_x', 'scale_y', 'scale_z',

            'render_queue', 'collision', 'collider', 'scripts')

#------------
# ANIMATIONS
#------------
    def animate(self, name, value, duration=.1, delay=0, curve=curve.in_expo, resolution=None, interrupt=True, time_step=None):
        s = Sequence(
            Wait(delay),
            Func(self._animate, name, value, duration, curve, resolution, interrupt, time_step)
        )
        s.start()
        return s

    def _animate(self, name, value, duration=.1, curve=curve.in_expo, resolution=None, interrupt=True, time_step=None):
        animator_name = name + '_animator'
        # print('start animating value:', name, animator_name )
        if interrupt and hasattr(self, animator_name):
            try:
                getattr(self, animator_name).pause()
                # print('interrupt', animator_name)
            except:
                pass
        else:
            try:
                getattr(self, animator_name).finish()
            except:
                pass
        setattr(self, animator_name, Sequence(time_step=time_step))
        sequence = getattr(self, animator_name)
        self.animations.append(sequence)
        # sequence.append(Wait(delay))
        if not resolution:
            resolution = max(int(duration * 60), 1)

        for i in range(resolution+1):
            t = i / resolution
            t = curve(t)

            sequence.append(Wait(duration / resolution))
            sequence.append(Func(setattr, self, name, lerp(getattr(self, name), value, t)))

        sequence.start()
        return sequence

    def animate_position(self, value, duration=.1, delay=0, curve=curve.in_expo, resolution=None, interrupt=True, time_step=None):
        x = self.animate('x', value[0], duration, delay, curve, resolution, interrupt, time_step)
        y =self.animate('y', value[1], duration, delay, curve, resolution, interrupt, time_step)
        z = None
        if len(value) > 2:
            z = self.animate('z', value[2], duration, delay, curve, resolution, interrupt, time_step)
        return x, y, z

    def animate_x(self, value, duration=.1, delay=0, curve=curve.in_expo, resolution=None, interrupt=True, time_step=None):
        return self.animate('x', value, duration, delay, curve, resolution, interrupt, time_step)
    def animate_y(self, value, duration=.1, delay=0, curve=curve.in_expo, resolution=None, interrupt=True, time_step=None):
        return self.animate('y', value, duration, delay, curve, resolution, interrupt, time_step)
    def animate_z(self, value, duration=.1, delay=0, curve=curve.in_expo, resolution=None, interrupt=True, time_step=None):
        return self.animate('z', value, duration, delay, curve, resolution, interrupt, time_step)


    def animate_rotation(self, value, duration=.1, delay=0, curve=curve.in_expo, resolution=None, interrupt=True, time_step=None):
        x = self.animate('rotation_x', value[0], duration, delay, curve, resolution, interrupt, time_step)
        y = self.animate('rotation_y', value[1], duration, delay, curve, resolution, interrupt, time_step)
        z = self.animate('rotation_z', value[2], duration, delay, curve, resolution, interrupt, time_step)
        return x, y, z
    def animate_rotation_x(self, value, duration=.1, delay=0, curve=curve.in_expo, resolution=None, interrupt=True, time_step=None):
        return self.animate('rotation_x', value, duration, delay, curve, resolution, interrupt, time_step)
    def animate_rotation_y(self, value, duration=.1, delay=0, curve=curve.in_expo, resolution=None, interrupt=True, time_step=None):
        return self.animate('rotation_y', value, duration, delay, curve, resolution, interrupt, time_step)
    def animate_rotation_z(self, value, duration=.1, delay=0, curve=curve.in_expo, resolution=None, interrupt=True, time_step=None):
        return self.animate('rotation_z', value, duration, delay, curve, resolution, interrupt, time_step)

    def animate_scale(self, value, duration=.1, delay=0, curve=curve.in_expo, resolution=None, interrupt=True, time_step=None):
        if isinstance(value, (int, float, complex)):
            value = Vec3(value, value, value)
        return self.animate('scale', value, duration, delay, curve, resolution, interrupt, time_step)
    def animate_scale_x(self, value, duration=.1, delay=0, curve=curve.in_expo, resolution=None, interrupt=True, time_step=None):
        return self.animate('scale_x', value, duration, delay, curve, resolution, interrupt, time_step)
    def animate_scale_y(self, value, duration=.1, delay=0, curve=curve.in_expo, resolution=None, interrupt=True, time_step=None):
        return self.animate('scale_y', value, duration, delay, curve, resolution, interrupt, time_step)
    def animate_scale_z(self, value, duration=.1, delay=0, curve=curve.in_expo, resolution=None, interrupt=True, time_step=None):
        return self.animate('scale_z', value, duration, delay, curve, resolution, interrup, time_stept)


    def shake(self, duration=.2, magnitude=1, speed=.05, direction=(1,1)):
        s = Sequence()
        self.original_position = self.position
        for i in range(int(duration / speed)):
            s.append(self.posInterval(speed, Point3(
                self.x + (random.uniform(-.1, .1) * magnitude * direction[0]),
                self.z,
                self.y + (random.uniform(-.1, .1) * magnitude * direction[1]))
            ))
            s.append(self.posInterval(speed, Point3(
                self.original_position[0],
                self.original_position[2],
                self.original_position[1])
            ))
        s.start()
        return s

    def animate_color(self, value, duration=.1, delay=0, curve=curve.in_expo, resolution=None, interrupt=False, time_step=None):
        return self.animate('color', value, duration, delay, curve, resolution, interrupt, time_step)

    def fade_out(self, value=0, duration=.5, delay=0, curve=curve.in_expo, resolution=None, interrupt=False, time_step=None):
        return self.animate('color', Vec4(self.color[0], self.color[1], self.color[2], value), duration, delay, curve, resolution, interrupt, time_step)

    def fade_in(self, value=1, duration=.5, delay=0, curve=curve.in_expo, resolution=None, interrupt=False, time_step=None):
        return self.animate('color', Vec4(self.color[0], self.color[1], self.color[2], value), duration, delay, curve, resolution, interrupt, time_step)

    def blink(self, value=color.clear, duration=.1, delay=0, curve=curve.in_expo, resolution=None, interrupt=False, time_step=None):
        _original_color = self.color
        if hasattr(self, 'blink_animator'):
            self.blink_animator.finish()
            self.blink_animator.kill()
            print('finish blink_animator')
        self.blink_animator = Sequence(
            Func(self.animate_color, value, duration*.4, 0, curve, resolution, interrupt),
            Func(self.animate_color, _original_color, duration*.4, duration*.5, curve, resolution, interrupt, time_step)
        )
        self.blink_animator.start()
        return self.blink_animator
        # self.animate_color(value, duration*.4, 0, curve, resolution, interrupt)
        # self.animate_color(_original_color, duration*.4, duration*.5, curve, resolution, interrupt)


if __name__ == '__main__':
    from ursina import *
    app = main.Ursina()
    import time
    t = time.time()
    # for i in range(1000):
    #     e = Entity(model='quad')
    # [Entity(model='quad') for i in range(1000)]
    #
    # # using Entity class with inheritance
    # class Player(Entity):
    #     def __init__(self):
    #         super().__init__()
    #         self.model='cube'
    #         self.color = color.orange
    #         self.scale_y = 2
    #
    #     # input and update functions gets automatically called by the engine
    #
    #     def input(self, key):
    #         if key == 'space':
    #             # self.color = self.color.inverse()
    #             self.animate_x(2, duration=1)
    #
    #     def update(self):
    #         self.x += held_keys['d'] * time.dt * 10
    #         self.x -= held_keys['a'] * time.dt * 10
    #
    # player = Player()
    #
    # Sky()
    # e = Entity(model='sphere', color=color.red, reflectivity=1, y=2.5)
    # e.generate_reflection_map()
    #
    # player.reflection_map = e.reflection_map
    # player.reflectivity = 1

    EditorCamera()
    # p = Entity(model=Cylinder(8), color=color.black)
    # e1 = Entity(parent=p, model='cube', color=color.pink)
    # e2 = Entity(parent=p, model='cube', color=color.lime, x=2, scale=2, rotation_z=45)
    # e3 = Entity(parent=e2, model='cube', color=color.yellow, y=2, scale=.5)
    # p.combine()
    e = Entity(model='quad', color=color.orange)

    def input(key):
        if key == 'space':
            # e.blink(color.red,
            #     resolution=10,
            #     curve=curve.linear
            #     )
            camera.overlay.blink(color.black, 1)


    print(time.time() - t)
    app.run()
