from Range import *
from mathutils import Vector
from collections import OrderedDict
import bgl
import aud
import os
import random

# Vertex Shader - Processa cada vértice da geometria base
vertex = """
out vertData {
    vec2 coord;
} vert;

void main(){
    // Passa as coordenadas de textura para o geometry shader
    vert.coord = gl_MultiTexCoord0.xy;
    gl_Position = gl_Vertex;
}
"""

# Geometry Shader - Gera partículas a partir da geometria base
geometry = """
in vertData {
    vec2 coord;
} vert[3];

out geomData {
    vec2 coord;
    float fade;
    float life_progress;
    vec3 color;
} geom;

uniform sampler2D bgl_DepthTexture;
uniform vec2 screen_size;

uniform float time;
uniform int emission_mode;
uniform int use_tracking;

uniform float ref_pos_x;
uniform float ref_pos_y;
uniform float ref_pos_z;

// Gera valor aleatório baseado em coordenadas
float getRand(vec2 coord){
    return fract(sin(dot(coord, vec2(12.9898, 78.233))) * 43758.5453);
}

// Converte coordenadas de tela para posição mundial usando depth buffer
vec3 getWorldPos(vec2 uv) {
    float depth = texture(bgl_DepthTexture, uv).r;
    return vec3((uv.x - 0.5) * 20.0, (uv.y - 0.5) * 20.0, depth * 10.0 - 5.0);
}

// Função para Billboard 2D (Screen-Aligned)
vec3 applyBillboard2D(vec3 position, vec2 vertex_offset, float scale) {
    vec3 camera_right = vec3(gl_ModelViewMatrix[0][0], gl_ModelViewMatrix[1][0], gl_ModelViewMatrix[2][0]);
    vec3 camera_up = vec3(gl_ModelViewMatrix[0][1], gl_ModelViewMatrix[1][1], gl_ModelViewMatrix[2][1]);
    
    return position + 
           camera_right * vertex_offset.x * scale + 
           camera_up * vertex_offset.y * scale;
}

// Função para Billboard 3D (World-Oriented)
vec3 applyBillboard3D(vec3 position, vec3 target, vec2 vertex_offset, float scale) {
    vec3 to_target = normalize(target - position);
    vec3 up = vec3(0.0, 0.0, 1.0);
    vec3 right = normalize(cross(up, to_target));
    vec3 real_up = normalize(cross(to_target, right));
    
    return position + 
           right * vertex_offset.x * scale + 
           real_up * vertex_offset.y * scale;
}

void main() {
    // Loop através de todas as partículas
    for (int j = 0; j < amount; j++) {
        // Calcula progresso da vida da partícula
        float life_progress = mod(time + float(j) * 0.1, life) / life;
        geom.life_progress = life_progress;
        
        // Gera ruído para variação
        float noise_x = getRand(vec2(j, 0.5));
        float noise_y = getRand(vec2(j, 1.3));
        
        // Calcula fade baseado no progresso da vida
        geom.fade = 1.0 - (life_progress / life);
        
        // Interpola cor do início ao fim com cor intermediária
        vec3 final_color;
        if (life_progress < 0.5) {
            // Primeira metade da vida: interpola entre start_color e mid_color
            float t = life_progress * 2.0;
            final_color = mix(start_color, mid_color, t);
        } else {
            // Segunda metade da vida: interpola entre mid_color e end_color
            float t = (life_progress - 0.5) * 2.0;
            final_color = mix(mid_color, end_color, t);
        }
        geom.color = final_color;

        // POSICIONAMENTO BASE
        vec3 base_position = vec3(0.0);
        
        // Seleciona modo de emissão
        if (emission_mode == 0) { 
            // Modo World: posição fixa no mundo
            base_position = world_emission_center;
        } else if (emission_mode == 1) { 
            // Modo Camera: posição relativa à câmera
            base_position = vec3(ref_pos_x, ref_pos_y, ref_pos_z);
        } else if (emission_mode == 2) { 
            // Modo Hybrid: baseado em depth buffer
            vec2 texcoord = vec2(
                float(j % int(screen_size.x)) / screen_size.x,
                float(j / int(screen_size.x)) / screen_size.y
            );
            base_position = getWorldPos(texcoord);
        }

        // MOVIMENTO BÁSICO
        vec3 movement = base_direction * movement_speed * life_progress;
        
        // DISPERSÃO para espalhar partículas
        vec3 dispersion = vec3(
            (noise_x * 2.0 - 1.0) * dispersion_area.x,
            (noise_y * 2.0 - 1.0) * dispersion_area.y,
            (getRand(vec2(j, 2.7)) * 2.0 - 1.0) * dispersion_area.z
        );

        // POSIÇÃO FINAL COM MOVIMENTO E DISPERSÃO
        vec3 final_position = base_position + movement + dispersion;

        // REINICIO quando a partícula chega ao fim da vida
        if (life_progress >= 1.0) {
            if (emission_mode == 0) final_position = world_emission_center;
            else if (emission_mode == 1) final_position = vec3(ref_pos_x, ref_pos_y, ref_pos_z);
        }

        // SISTEMA DE BILLBOARD/TrackTo
        if (use_tracking == 1 && rotate_movement == 1) {
            vec3 target_pos = vec3(ref_pos_x, ref_pos_y, ref_pos_z);
            float current_scale = scale_start + (scale_end - scale_start) * life_progress;
            
            if (billboard_mode == 1) {
                // BILLBOARD 2D - sempre olha para a câmera
                for (int i = 0; i < 3; i++) {
                    geom.coord = vert[i].coord;
                    vec4 vertex = gl_in[i].gl_Position;
                    
                    vec3 billboard_pos = applyBillboard2D(final_position, vertex.xy, current_scale);
                    vertex.xyz = billboard_pos;
                    
                    gl_Position = gl_ProjectionMatrix * gl_ModelViewMatrix * vertex;
                    EmitVertex();
                }
                EndPrimitive();
            }
            else if (billboard_mode == 2) {
                // BILLBOARD 3D - olha para o objeto alvo
                for (int i = 0; i < 3; i++) {
                    geom.coord = vert[i].coord;
                    vec4 vertex = gl_in[i].gl_Position;
                    
                    vec3 billboard_pos = applyBillboard3D(final_position, target_pos, vertex.xy, current_scale);
                    vertex.xyz = billboard_pos;
                    
                    gl_Position = gl_ProjectionMatrix * gl_ModelViewMatrix * vertex;
                    EmitVertex();
                }
                EndPrimitive();
            }
            else {
                // ROTAÇÃO TRADICIONAL - comportamento padrão
                mat2 face_rotation = mat2(1.0);
                vec3 to_target = target_pos - final_position;
                
                if (length(to_target) > 0.1) {
                    vec3 dir_normalized = normalize(to_target);
                    float target_angle = atan(dir_normalized.x, dir_normalized.y);
                    
                    face_rotation = mat2(
                        cos(target_angle), -sin(target_angle),
                        sin(target_angle), cos(target_angle)
                    );
                }

                for (int i = 0; i < 3; i++) {
                    geom.coord = vert[i].coord;
                    vec4 vertex = gl_in[i].gl_Position;
                    
                    float current_scale = scale_start + (scale_end - scale_start) * life_progress;
                    vertex.xy *= current_scale;
                    vertex.xy = face_rotation * vertex.xy;
                    vertex.xyz += final_position;
                    
                    gl_Position = gl_ProjectionMatrix * gl_ModelViewMatrix * vertex;
                    EmitVertex();
                }
                EndPrimitive();
            }
        } else {
            // COMPORTAMENTO NORMAL - sem trackTo
            for (int i = 0; i < 3; i++) {
                geom.coord = vert[i].coord;
                vec4 vertex = gl_in[i].gl_Position;
                
                float current_scale = scale_start + (scale_end - scale_start) * life_progress;
                vertex.xy *= current_scale;
                vertex.xyz += final_position;
                
                gl_Position = gl_ProjectionMatrix * gl_ModelViewMatrix * vertex;
                EmitVertex();
            }
            EndPrimitive();
        }
    }
}
"""

# Fragment Shader - Processa cor e transparência de cada pixel
fragment = """
in geomData {
    vec2 coord;
    float fade;
    float life_progress;
    vec3 color;
} geom;

uniform sampler2D textures[7];
uniform int texture_count;

void main() {
    // Amostra textura base
    vec4 tex_color = texture(textures[0], geom.coord);
    
    // Sequência de texturas baseada no tempo de vida
    for (int i = 0; i < texture_count; i++) {
        if (geom.life_progress > (1.0 / float(texture_count)) * float(i)) {
            tex_color = texture(textures[i], geom.coord);
        }
    }

    // Aplica cor e transparência
    gl_FragColor.rgb = tex_color.rgb * geom.color;
    gl_FragColor.a = tex_color.r * geom.fade;
}
"""

class AdvancedParticleSystem(types.KX_PythonComponent):
    # Define os argumentos configuráveis do componente
    args = OrderedDict([
        # Ativadores e identificadores da partícula
        ("activateParticle", False),

        # Configurações Básicas
        ("amount", 100),  # Número de partículas
        ("life", 5.0),    # Duração de vida em segundos
        
        # SISTEMA DE EMISSÃO
        ("emission_mode", {"World", "Camera", "Hybrid"}),  # Modo de emissão
        ("world_emission_center", Vector((0, 0, 0))),     # Centro de emissão para modo World
        ("reference_object", "Camera"),                   # Objeto de referência para modo Camera
        
        # MOVIMENTO
        ("base_direction", Vector((0, 1, 0))),           # Direção base do movimento
        ("movement_speed", 1.0),                         # Velocidade do movimento
        ("rotate_movement", False),                      # Se rotaciona com a câmera
        
        # SISTEMA DE BILLBOARD
        ("billboard_mode", {"Nenhum", "2D", "3D"}),      # Tipo de billboard
        ("billboard_size", Vector((1.0, 1.0, 0.0))),     # Tamanho do billboard
        
        # DISPERSÃO  
        ("dispersion_area", Vector((2.0, 2.0, 1.0))),   # Área de dispersão
        
        # ESCALA
        ("scale_start", 0.1),  # Escala inicial
        ("scale_end", 0.3),    # Escala final
        
        # CORES - Agora com três cores: início, meio e fim
        ("start_color", Vector((1, 0.5, 0.2))),  # Cor inicial (Laranja)
        ("mid_color", Vector((1, 0.8, 0.1))),    # Cor intermediária (Amarelo-alaranjado)
        ("end_color", Vector((1, 0, 0))),        # Cor final (Vermelho)
        
        # FADE
        ("fade_in", 0.2),   # 20% da vida para fade in
        ("fade_out", 0.3),  # 30% da vida para fade out

        # SISTEMA DE ÁUDIO
        ("audio_file", ""),  # Arquivo de áudio principal
        ("audio_behavior", {"Nenhum", "Contínuo", "Uma Vez", "Aleatório"}),  # Comportamento do áudio
        ("audio_volume", 0.7),       # Volume (0.0 a 1.0)
        ("min_interval", 5.0),       # Intervalo mínimo para áudio aleatório
        ("max_interval", 15.0),      # Intervalo máximo para áudio aleatório
        ("audio_files_random", ""),  # Lista de arquivos para randomização
    ])
    
    def awake(self, args):
        """
        Inicialização do componente quando o objeto é criado
        """
        # Configura estado inicial baseado na configuração
        if args["activateParticle"]:
            self.active = True
            self.object.setVisible(True)
            self.activate_system()
        else:
            # Inicia desativado - será ativado pelo ClimaControl quando necessário
            self.active = False
            self.object.setVisible(False)
            
        # Armazena configurações para uso posterior
        self.args = args
        
        # Inicializa sistema de áudio
        self.audio_device = aud.Device()
        self.audio_handle = None
        self.audio_buffers = []
        self.last_audio_time = 0.0
        self.next_audio_time = 0.0
        self.audio_initialized = False
        
        # Configura sistema de áudio
        self.initialize_audio_system(args)

        # Inicialização do shader - será feito na primeira ativação
        self.shader = None
        self.shader_compiled = False
        self.cam = self.object.scene.active_camera
        
        # Obtém referência do material do objeto
        self.mat = self.object.meshes[0].materials[0] if self.object.meshes and self.object.meshes[0].materials else None
        
        # Debug da geometria do objeto
        if self.object.meshes:
            mesh = self.object.meshes[0]
            print(f"GEOMETRIA: {mesh.name}")
            print(f"Vertices: {len(mesh.vertices) if hasattr(mesh, 'vertices') else 'N/A'}")
            print(f"Poligonos: {len(mesh.polygons) if hasattr(mesh, 'polygons') else 'N/A'}")
            print(f"Material: {self.mat.name if self.mat else 'Nenhum'}")
        
        # Configura objeto de referência para tracking
        self.ref_obj = None
        if args["reference_object"]:
            self.ref_obj = self.object.scene.objects.get(args["reference_object"])
        
        print(f"{self.object.name}: Sistema de partículas inicializado (INATIVO)")
    
    def iniciarAtivado(self):
        """
        Método para verificar se o sistema deve iniciar ativado
        Retorna: Boolean indicando se estava configurado para iniciar ativo
        """
        self.iniciar_ativado = self.args["activateParticle"]
        self.active = True
        self.activate_system()
        return self.iniciar_ativado
    
    def initialize_audio_system(self, args):
        """
        Inicializa o sistema de áudio baseado nas configurações
        """
        base_path = logic.expandPath("//")
        
        # Carrega áudio principal se especificado
        if args["audio_file"]:
            audio_path = os.path.join(base_path, args["audio_file"])
            if os.path.exists(audio_path):
                audio_buffer = aud.Sound(audio_path)
                audio_buffer = aud.Sound.cache(audio_buffer)
                self.audio_buffers.append(audio_buffer)
                print(f"Audio principal carregado: {audio_path}")
            else:
                print(f"Erro: Arquivo de audio não encontrado: {audio_path}")
        
        # Carrega lista de áudios para randomização
        if args["audio_files_random"]:
            audio_files = [f.strip() for f in args["audio_files_random"].split(',') if f.strip()]
            for audio_file in audio_files:
                audio_path = os.path.join(base_path, audio_file)
                if os.path.exists(audio_path):
                    audio_buffer = aud.Sound(audio_path)
                    audio_buffer = aud.Sound.cache(audio_buffer)
                    self.audio_buffers.append(audio_buffer)
                    print(f"Audio randomizado carregado: {audio_path}")
                else:
                    print(f"Erro: Arquivo de audio randomizado não encontrado: {audio_path}")
        
        # Configura comportamento do áudio
        self.audio_behavior = args["audio_behavior"]
        self.audio_volume = args["audio_volume"]
        self.min_interval = args["min_interval"]
        self.max_interval = args["max_interval"]
        self.audio_initialized = len(self.audio_buffers) > 0
        
        if self.audio_initialized:
            print(f"Sistema de audio inicializado: {len(self.audio_buffers)} arquivos, comportamento: {self.audio_behavior}")

    def compile_shader(self):
        """
        Compila o shader apenas quando necessário
        Retorna: Boolean indicando sucesso
        """
        if not self.mat:
            print(f"{self.object.name}: Não há material para compilar shader")
            return False
            
        print(f"{self.object.name}: Compilando shader...")
        
        # Calcula número máximo de vértices baseado na quantidade de partículas
        value = min(self.args["amount"] * 3, 1023)
        
        # Define constantes do shader baseado nas configurações
        const = f"""
        layout(triangles) in;
        layout(triangle_strip, max_vertices = {value}) out;

        const int amount = {self.args["amount"]};
        const float life = {self.args["life"]};
        const float scale_start = {self.args["scale_start"]};
        const float scale_end = {self.args["scale_end"]};
        const float movement_speed = {self.args["movement_speed"]};
        const float fade_in = {self.args["fade_in"]};
        const float fade_out = {self.args["fade_out"]};
        const vec3 base_direction = vec3({self.args["base_direction"][0]}, {self.args["base_direction"][1]}, {self.args["base_direction"][2]});
        const int rotate_movement = {1 if self.args["rotate_movement"] else 0};
        const int billboard_mode = {0 if self.args["billboard_mode"] == "Nenhum" else 1 if self.args["billboard_mode"] == "2D" else 2};
        const vec3 dispersion_area = vec3({self.args["dispersion_area"][0]}, {self.args["dispersion_area"][1]}, {self.args["dispersion_area"][2]});
        const vec3 start_color = vec3({self.args["start_color"][0]}, {self.args["start_color"][1]}, {self.args["start_color"][2]});
        const vec3 mid_color = vec3({self.args["mid_color"][0]}, {self.args["mid_color"][1]}, {self.args["mid_color"][2]});
        const vec3 end_color = vec3({self.args["end_color"][0]}, {self.args["end_color"][1]}, {self.args["end_color"][2]});
        const vec3 world_emission_center = vec3({self.args["world_emission_center"][0]}, {self.args["world_emission_center"][1]}, {self.args["world_emission_center"][2]});
        """

        # Combina shaders com constantes
        sources = {
            "vertex": vertex,
            "geometry": const + geometry,
            "fragment": fragment
        }
        
        # Obtém referência do shader do material
        self.shader = self.mat.getShader()
        
        if self.shader is not None:
            # Compila shader se não for válido
            if not self.shader.isValid():
                self.shader.setSourceList(sources, 1)
                
            # Configura texturas do material
            texture_count = 0
            for i, tex in enumerate(self.mat.textures):
                if tex and hasattr(tex, 'name'):
                    self.shader.setSampler(f"textures[{i}]", i)
                    texture_count += 1
            self.shader.setUniform1i("texture_count", texture_count)

            # Configura textura de depth buffer
            self.shader.setSampler("bgl_DepthTexture", 1)
            
            # Configurações de tela
            self.shader.setUniform2f("screen_size", render.getWindowWidth(), render.getWindowHeight())
            
            # Uniformes básicos
            self.shader.setUniform1f("ref_pos_x", 0.0)
            self.shader.setUniform1f("ref_pos_y", 0.0)
            self.shader.setUniform1f("ref_pos_z", 0.0)
            self.shader.setUniform1i("use_tracking", 0)
            self.shader.setUniform1i("billboard_mode", 0)
            
            print(f"{self.object.name}: Shader compilado com sucesso")
            return True
        else:
            print(f"{self.object.name}: Falha ao obter shader")
            return False

    def set_billboard_mode(self, mode):
        """
        Altera o modo de billboard em tempo de execução
        """
        valid_modes = {"Nenhum", "2D", "3D"}
        if mode in valid_modes:
            self.args["billboard_mode"] = mode
            # Recompila o shader para aplicar as mudanças
            if self.shader_compiled:
                self.compile_shader()
            print(f"{self.object.name}: Modo billboard alterado para: {mode}")
        else:
            print(f"Modo inválido. Use: {valid_modes}")

    def set_reference_object(self, obj_name):
        """
        Altera o objeto de referência em tempo de execução
        """
        if obj_name and obj_name != "":
            new_ref = self.object.scene.objects.get(obj_name)
            if new_ref:
                self.ref_obj = new_ref
                self.args["reference_object"] = obj_name
                print(f"{self.object.name}: Objeto de referência alterado para: {obj_name}")
            else:
                print(f"{self.object.name}: Objeto de referência não encontrado: {obj_name}")
        else:
            self.ref_obj = None
            print(f"{self.object.name}: Tracking desativado")

    def toggle_tracking(self, enable):
        """
        Ativa/desativa o tracking em tempo de execução
        """
        self.args["rotate_movement"] = enable
        print(f"{self.object.name}: Tracking {'ativado' if enable else 'desativado'}")
        
    def activate_system(self):
        """
        Ativa o sistema de partículas e compila o shader se necessário
        """
        if self.active:
            return
            
        self.active = True
        self.object.setVisible(True)
        
        # Compila shader apenas na primeira ativação
        if not self.shader_compiled and self.mat:
            success = self.compile_shader()
            if success:
                self.shader_compiled = True
            else:
                print(f"{self.object.name}: Falha na compilação do shader, desativando sistema")
                self.active = False
                self.object.setVisible(False)
                return
        
        # Inicia áudio se configurado
        if self.audio_initialized and self.audio_buffers:
            if self.audio_behavior == "Contínuo":
                self.play_audio(self.audio_buffers[0], True)
            elif self.audio_behavior == "Uma Vez":
                self.play_audio(self.audio_buffers[0], False)
        
        print(f"{self.object.name}: Sistema de partículas ATIVADO (shader_compiled: {self.shader_compiled})")

    def deactivate_system(self):
        """
        Desativa completamente o sistema de partículas
        """
        if not self.active:
            return
            
        self.active = False
        self.object.setVisible(False)
        
        # Para áudio
        self.stop_audio()
        
        print(f"{self.object.name}: Sistema de partículas DESATIVADO")

    def start(self, args):
        """
        Chamado quando o componente é iniciado
        """
        print(f"{self.object.name}: Sistema pronto (aguardando ativação)")

    def play_audio(self, audio_buffer, loop=False):
        """
        Reproduz um áudio com as configurações atuais
        """
        if self.audio_handle and self.audio_handle.status == aud.STATUS_PLAYING:
            self.audio_handle.stop()
            
        self.audio_handle = self.audio_device.play(audio_buffer)
        if loop:
            self.audio_handle.loop_count = -1  # Loop infinito
        self.audio_handle.volume = self.audio_volume
        
        return self.audio_handle

    def play_random_audio(self):
        """
        Reproduz um áudio aleatório da lista
        """
        if not self.audio_buffers:
            return
            
        audio_buffer = random.choice(self.audio_buffers)
        self.play_audio(audio_buffer, False)
        print(f"Reproduzindo audio aleatório: {len(self.audio_buffers)} opções disponíveis")

    def update_audio_system(self):
        """
        Atualiza o sistema de áudio baseado no comportamento configurado
        """
        # Verificação de segurança
        if not hasattr(self, 'audio_initialized') or not self.audio_initialized:
            return
            
        current_time = logic.getFrameTime()
        
        # Comportamento ALEATÓRIO
        if self.audio_behavior == "Aleatório":
            if current_time >= self.next_audio_time:
                self.play_random_audio()
                interval = random.uniform(self.min_interval, self.max_interval)
                self.next_audio_time = current_time + interval

        # Comportamento CONTÍNUO
        elif self.audio_behavior == "Contínuo":
            if (self.audio_handle and 
                self.audio_handle.status != aud.STATUS_PLAYING and 
                self.audio_buffers):
                self.play_audio(self.audio_buffers[0], True)

    def stop_audio(self):
        """
        Para qualquer áudio que esteja tocando
        """
        if self.audio_handle and self.audio_handle.status == aud.STATUS_PLAYING:
            self.audio_handle.stop()
            self.audio_handle = None

    def update(self):
        """
        Chamado a cada frame para atualizar o sistema
        """
        # Verifica se precisa compilar o shader
        if self.active and not self.shader_compiled and self.mat:
            success = self.compile_shader()
            if success:
                self.shader_compiled = True
            else:
                print(f"{self.object.name}: Falha na compilação do shader")
                self.active = False
                self.object.setVisible(False)
                return
        
        # Retorna se não estiver ativo
        if not self.active or not self.shader_compiled:
            return
            
        
        # Atualiza sistema de áudio
        if self.audio_initialized:
            self.update_audio_system()

        # Atualiza tempo do shader
        if self.shader:
            self.shader.setUniform1f("time", logic.getFrameTime())
                
        # Atualização dos uniforms de tracking
        if self.shader and self.shader.isValid():
            if self.ref_obj:
                try:
                    ref_pos = self.ref_obj.worldPosition
                    
                    # Debug periódico do tracking
                    current_time = logic.getFrameTime()
                    if int(current_time) % 3 == 0 and int(current_time) != getattr(self, 'last_debug_time', 0):
                        self.last_debug_time = int(current_time)
                        
                        particle_pos = self.object.worldPosition
                        direction = ref_pos - particle_pos
                        distance = direction.length
                        
                        print(f"DEBUG TRACKING:")
                        print(f"   Particula: {particle_pos}")
                        print(f"   Alvo: {ref_pos}")
                        print(f"   Direção: ({direction.x:.2f}, {direction.y:.2f}, {direction.z:.2f})")
                        print(f"   Distância: {distance:.1f}")
                        print(f"   use_tracking: {1}, rotate_movement: {self.args['rotate_movement']}")
                        
                        if self.shader:
                            print(f"   Shader válido: {self.shader.isValid()}")
                    
                    # Atualiza uniforms de posição
                    self.shader.setUniform1f("ref_pos_x", ref_pos.x)
                    self.shader.setUniform1f("ref_pos_y", ref_pos.y)
                    self.shader.setUniform1f("ref_pos_z", ref_pos.z)
                    self.shader.setUniform1i("use_tracking", 1)
                    
                except Exception as e:
                    print(f"Erro no tracking: {e}")
            else:
                self.shader.setUniform1i("use_tracking", 0)

    def change_audio_behavior(self, new_behavior, new_volume=None):
        """
        Muda o comportamento do áudio em tempo de execução
        """
        self.audio_behavior = new_behavior
        if new_volume is not None:
            self.audio_volume = new_volume
            if self.audio_handle:
                self.audio_handle.volume = self.audio_volume
        
        # Reinicia sistema baseado no novo comportamento
        self.stop_audio()
        if new_behavior == "Contínuo" and self.audio_buffers:
            self.play_audio(self.audio_buffers[0], True)
        
        print(f"Comportamento de audio alterado para: {new_behavior}")

    def add_audio_file(self, audio_path):
        """
        Adiciona um novo arquivo de áudio ao sistema
        """
        base_path = logic.expandPath("//")
        full_path = os.path.join(base_path, audio_path)
        
        if os.path.exists(full_path):
            audio_buffer = aud.Sound(full_path)
            audio_buffer = aud.Sound.cache(audio_buffer)
            self.audio_buffers.append(audio_buffer)
            self.audio_initialized = True
            print(f"Audio adicionado: {audio_path}")
            return True
        else:
            print(f"Erro: Arquivo de audio não encontrado: {audio_path}")
            return False
        
    def debug_tracking(self):
        """
        Debug para verificar se o tracking está funcionando
        """
        if self.ref_obj:
            ref_pos = self.ref_obj.worldPosition
            part_pos = self.object.worldPosition
            
            # Calcula a direção da partícula para o alvo
            direction = ref_pos - part_pos
            distance = direction.length
            
            print(f"DEBUG Tracking:")
            print(f"   Particula: {part_pos}")
            print(f"   Alvo: {ref_pos}") 
            print(f"   Direção: {direction.normalized()}")
            print(f"   Distância: {distance:.2f}")