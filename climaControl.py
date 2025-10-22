from Range import *
from collections import OrderedDict
import random
import time

class ClimaControl(types.KX_PythonComponent):
    args = OrderedDict([
        ("Duração mínima clima (min)", 0.1),
        ("Duração máxima clima (min)", 0.2),
        ("Chance de chuva (%)", 15),
        ("Chance de neve (%)", 30),
        ("Debug", True),
        ("Debug Detalhado", True),
    ])

    def start(self, args):
        self.active = self.object.get("activate", False)
        self.duracao_min = args["Duração mínima clima (min)"] * 60
        self.duracao_max = args["Duração máxima clima (min)"] * 60
        self.chance_chuva = args["Chance de chuva (%)"]
        self.chance_neve = args["Chance de neve (%)"]
        self.debug = args["Debug"]
        self.debug_detalhado = args["Debug Detalhado"]
        
        self.timer = 0.0
        self.clima_atual = self.object.get("clima_atual", "ensolarado")
        self.duracao_atual = random.uniform(self.duracao_min, self.duracao_max)
        self.last_time = time.time()
        self.last_clima_check = self.last_time
        self.last_debug_time = self.last_time
        
        self.sistemas_particulas = {}
        self.proximo_clima = None
        self.tempo_restante = self.duracao_atual
        
        if self.debug:
            print(f"🔧 INICIALIZANDO SISTEMA DE CLIMA")
            print(f"   Duração: {self.duracao_min/60:.1f}min a {self.duracao_max/60:.1f}min")
            print(f"   Clima inicial: {self.clima_atual}")
            print(f"   Active: {self.active}")
        
        self.coletar_sistemas_particulas_por_nome()
        self.definir_clima_inicial(self.clima_atual)
        
        self.proximo_clima = self.determinar_proximo_clima()
        
        if self.debug:
            self.mostrar_info_clima()

    def definir_clima_inicial(self, clima):
        """Define o clima inicial desativando todos os sistemas primeiro"""
        if self.debug:
            print(f"\n🌤️  DEFININDO CLIMA INICIAL: {clima}")

        sistemas_por_clima = {
            "chuvoso": ["chuva"],
            "nevando": ["neve"], 
            "seco": ["poeira", "folhas"],
            "nublado": ["nevoa"],
            "ensolarado": ["folhas"]
        }
        
        # 🔥 Desativa todos os sistemas primeiro
        for tipo, sistemas in self.sistemas_particulas.items():
            for sistema in sistemas:
                sistema['componente'].deactivate_system()
        
        # ✅ Ativa apenas os sistemas do clima inicial
        tipos_ativar = sistemas_por_clima.get(clima, [])
        for tipo in tipos_ativar:
            if tipo in self.sistemas_particulas:
                for sistema in self.sistemas_particulas[tipo]:
                    sistema['componente'].activate_system()
                    if self.debug_detalhado:
                        print(f"   ✅ Ativado (inicial): {sistema['objeto'].name} ({tipo})")

        self.clima_atual = clima
        self.object["clima_atual"] = clima

    def extrair_tipo_por_nome(self, nome_objeto):
        """Extrai o tipo de partícula baseado no nome do objeto - VERSÃO CORRIGIDA"""
        nome_lower = nome_objeto.lower().strip()
        
        # 🔥 ORDEM IMPORTANTE: termos mais específicos primeiro
        mapeamento_tipos = [
            ("neve", ["snow", "nevando", "neve_", "_neve"]),
            ("chuva", ["rain", "chuvando", "chuva_", "_chuva"]),
            ("nevoa", ["fog", "mist", "nevoa", "nevoeiro"]),
            ("poeira", ["dust", "poeira"]),
            ("folhas", ["leaves", "leaf", "folhas"])
        ]
        
        for tipo, palavras_chave in mapeamento_tipos:
            for palavra in palavras_chave:
                if palavra in nome_lower:
                    if self.debug_detalhado:
                        print(f"   ✅ {nome_objeto} → '{tipo}' (palavra-chave: '{palavra}')")
                    return tipo
        
        if self.debug_detalhado:
            print(f"   ❌ {nome_objeto} → NÃO CLASSIFICADO")
        return None

    def coletar_sistemas_particulas_por_nome(self):
        """Coleta sistemas de partículas baseado no nome do objeto - VERSÃO CORRIGIDA"""
        self.sistemas_particulas = {}
        sistemas_encontrados = 0
        
        for obj in self.object.scene.objects:
            if "AdvancedParticleSystem" in obj.components:
                componentes = obj.components["AdvancedParticleSystem"]
                if not componentes:
                    continue
                    
                comp = componentes
                tipo = self.extrair_tipo_por_nome(obj.name)
                
                if tipo is None:
                    if self.debug_detalhado:
                        print(f"   Ignorado: {obj.name} - tipo não identificado")
                    continue
                
                if tipo not in self.sistemas_particulas:
                    self.sistemas_particulas[tipo] = []
                
                self.sistemas_particulas[tipo].append({
                    'objeto': obj,
                    'componente': comp
                })
                sistemas_encontrados += 1
                
                # 🔥 DESATIVA CADA SISTEMA ENCONTRADO
                if comp.iniciarAtivado():
                    print("sistema individual ativo {obj.name}, componente {comp}")
                comp.deactivate_system()
                
                if self.debug_detalhado:
                    print(f"   Coletado e DESATIVADO: {obj.name} → '{tipo}'")
        
        if self.debug:
            print(f"   Sistemas coletados: {sistemas_encontrados}")
            print(f"   Tipos: {list(self.sistemas_particulas.keys())}")

    def calcular_probabilidades(self):
        """Calcula as probabilidades de cada tipo de clima"""
        prob_precipitacao = self.chance_chuva + self.chance_neve
        prob_restante = max(0, 100 - prob_precipitacao)
        
        opcoes_nao_precipitacao = ["ensolarado", "seco", "nublado"]
        prob_por_clima = prob_restante / len(opcoes_nao_precipitacao) if opcoes_nao_precipitacao else 0
        
        probabilidades = {
            "chuvoso": self.chance_chuva,
            "nevando": self.chance_neve,
            "ensolarado": prob_por_clima,
            "seco": prob_por_clima,
            "nublado": prob_por_clima
        }
        
        # ✅ Ajusta para garantir que a soma seja 100%
        soma_atual = sum(probabilidades.values())
        if soma_atual != 100:
            ajuste = (100 - soma_atual) / len(probabilidades)
            for clima in probabilidades:
                probabilidades[clima] += ajuste
        
        return probabilidades

    def determinar_proximo_clima(self):
        """Determina o próximo clima baseado nas probabilidades"""
        prob_precipitacao = self.chance_chuva + self.chance_neve
        rand = random.random() * 100
        
        if rand < prob_precipitacao:
            if rand < self.chance_chuva:
                return "chuvoso"
            else:
                return "nevando"
        
        opcoes = ["ensolarado", "seco", "nublado"]
        return random.choice(opcoes)

    def mostrar_info_clima(self):
        """Mostra informações detalhadas sobre o estado do clima"""
        probabilidades = self.calcular_probabilidades()
        
        print("\n" + "="*50)
        print("🌤️  SISTEMA DE CLIMA - INFORMAÇÕES DETALHADAS")
        print("="*50)
        print(f"Clima Atual: {self.clima_atual.upper()}")
        print(f"Próximo Clima: {self.proximo_clima.upper()}")
        print(f"Timer: {self.timer:.1f}s / {self.duracao_atual:.1f}s")
        print(f"Tempo Restante: {self.tempo_restante/60:.1f}min ({self.tempo_restante:.0f}s)")
        
        print("\n📊 PROBABILIDADES:")
        for clima, prob in probabilidades.items():
            seta = "← PRÓXIMO" if clima == self.proximo_clima else ""
            print(f"  {clima.capitalize()}: {prob:.1f}% {seta}")
        
        print("\n🎯 SISTEMAS DE PARTÍCULAS ATIVOS:")
        sistemas_por_clima = {
            "chuvoso": ["chuva"],
            "nevando": ["neve"], 
            "seco": ["poeira", "folhas"],
            "nublado": ["nevoa"],
            "ensolarado": ["folhas"]
        }
        
        tipos_necessarios = sistemas_por_clima.get(self.clima_atual, [])
        for tipo in tipos_necessarios:
            if tipo in self.sistemas_particulas:
                status = f"✓ ENCONTRADO ({len(self.sistemas_particulas[tipo])} sistemas)"
            else:
                status = "✗ NÃO ENCONTRADO"
            print(f"  {tipo.capitalize()}: {status}")
        
        print("="*50)

    def definir_clima(self, novo_clima):
        if novo_clima == self.clima_atual:
            return
            
        if self.debug:
            print(f"\n🔄 MUDANÇA DE CLIMA: {self.clima_atual} → {novo_clima}")

        sistemas_por_clima = {
            "chuvoso": ["chuva"],
            "nevando": ["neve"], 
            "seco": ["poeira", "folhas"],
            "nublado": ["nevoa"],
            "ensolarado": ["folhas"]
        }
        
        tipos_ativar = sistemas_por_clima.get(novo_clima, [])
        tipos_desativar = sistemas_por_clima.get(self.clima_atual, [])
        
        # 🔥 CORREÇÃO: Desativar apenas os tipos que NÃO serão reutilizados
        for tipo in tipos_desativar:
            if tipo not in tipos_ativar and tipo in self.sistemas_particulas:
                for sistema in self.sistemas_particulas[tipo]:
                    sistema['componente'].deactivate_system()
                    if self.debug_detalhado:
                        print(f"   ❌ Desativado: {sistema['objeto'].name} ({tipo})")

        # ✅ DEPOIS: Ativar novos sistemas
        for tipo in tipos_ativar:
            if tipo in self.sistemas_particulas:
                for sistema in self.sistemas_particulas[tipo]:
                    sistema['componente'].activate_system()
                    if self.debug_detalhado:
                        print(f"   ✅ Ativado: {sistema['objeto'].name} ({tipo})")

        self.clima_atual = novo_clima
        self.object["clima_atual"] = novo_clima
        
        # Resetar timer
        current_time = time.time()
        self.timer = 0.0
        self.last_time = current_time
        self.duracao_atual = random.uniform(self.duracao_min, self.duracao_max)
        self.tempo_restante = self.duracao_atual
        self.proximo_clima = self.determinar_proximo_clima()
        
        if self.debug:
            print(f"✅ Clima alterado: {novo_clima}")

    def update(self):
        if not self.active:
            if self.debug_detalhado and random.random() < 0.01:
                print("❌ Sistema de clima INATIVO")
            return
            
        current_time = time.time()
        delta_time = current_time - self.last_time
        self.last_time = current_time
        self.timer += delta_time
        self.tempo_restante = max(0, self.duracao_atual - self.timer)
        
        # Debug detalhado do timer
        if self.debug_detalhado and int(current_time) % 5 == 0:
            print(f"⏰ Timer: {self.timer:.1f}/{self.duracao_atual:.1f}s - Restante: {self.tempo_restante:.1f}s")
        
        # Mostra info completa a cada 30 segundos
        if self.debug and current_time - self.last_debug_time >= 30.0:
            self.last_debug_time = current_time
            self.mostrar_info_clima()
        
        # ✅ CORREÇÃO: Verifica mudança de clima continuamente
        if self.timer >= self.duracao_atual:
            if self.debug:
                print(f"\n🎯 TEMPO ESGOTADO! Mudando clima...")
                print(f"   Timer: {self.timer:.1f}s, Duração: {self.duracao_atual:.1f}s")
            
            # ✅ RESET imediato do timer ANTES de mudar o clima
            self.timer = 0.0
            novo_clima = self.proximo_clima
            self.definir_clima(novo_clima)