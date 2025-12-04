// app/static/js/auth.js - Versión mejorada sin autenticación
class AuthManager {
    constructor() {
        this.user = {
            id: 1,
            username: "anonymous",
            role: "customer",
            is_superuser: false,
            authenticated: false
        };
        this.init();
    }
    
    async init() {
        console.log('AuthManager iniciado (sin autenticación)');
        this.triggerAuthChange();
        this.setupEventListeners();
        this.checkCurrentPage();
    }
    
    // Función para verificar la página actual y mostrar mensajes apropiados
    checkCurrentPage() {
        // Si estamos en una página que normalmente requiere autenticación,
        // mostrar un mensaje informativo
        const pagesRequiringInfo = ['/mi-carrito', '/mis-pedidos', '/perfil'];
        const currentPath = window.location.pathname;
        
        if (pagesRequiringInfo.includes(currentPath)) {
            this.showInfoMessage();
        }
    }
    
    showInfoMessage() {
        // Crear y mostrar un mensaje informativo
        const message = `
            <div class="card-panel blue lighten-5" style="margin: 10px 0; border-left: 4px solid #2196f3;">
                <div style="display: flex; align-items: center;">
                    <i class="material-icons blue-text" style="margin-right: 10px;">info</i>
                    <div>
                        <strong>Modo sin autenticación</strong>
                        <p style="margin: 5px 0 0 0; font-size: 0.9rem;">
                            Estás usando el sistema sin necesidad de iniciar sesión. 
                            <a href="/usuarios" style="text-decoration: underline;">Puedes crear usuarios</a> si lo deseas.
                        </p>
                    </div>
                </div>
            </div>
        `;
        
        // Insertar mensaje después del navbar
        const navbar = document.querySelector('nav');
        if (navbar) {
            const container = document.createElement('div');
            container.innerHTML = message;
            navbar.parentNode.insertBefore(container, navbar.nextSibling);
        }
    }
    
    // Funciones dummy para mantener compatibilidad
    isAuthenticated() {
        return false; // Nunca autenticado
    }
    
    hasRole(role) {
        // Por defecto todos son "customer" para permitir acceso
        return role === "customer";
    }
    
    isAdmin() {
        return false;
    }
    
    isVendor() {
        return false;
    }
    
    isCustomer() {
        return true; // Todos son clientes por defecto
    }
    
    triggerAuthChange() {
        const event = new CustomEvent('auth-change', {
            detail: { 
                user: this.user, 
                authenticated: false,
                isAdmin: false,
                isVendor: false,
                isCustomer: true
            }
        });
        window.dispatchEvent(event);
    }
    
    setupEventListeners() {
        // Interceptar enlaces que requieren autenticación y permitirlos
        document.addEventListener('click', (e) => {
            const link = e.target.closest('[data-require-auth]');
            if (link) {
                e.preventDefault();
                // Mostrar mensaje informativo
                M.toast({
                    html: 'Acceso permitido en modo sin autenticación',
                    classes: 'blue',
                    displayLength: 3000
                });
                // Permitir acceso
                setTimeout(() => {
                    window.location.href = link.href;
                }, 500);
            }
        });
        
        // Permitir todos los roles
        document.addEventListener('click', (e) => {
            const link = e.target.closest('[data-require-role]');
            if (link) {
                e.preventDefault();
                // Mostrar mensaje informativo
                M.toast({
                    html: 'Todos los roles están permitidos en este modo',
                    classes: 'blue',
                    displayLength: 3000
                });
                // Permitir acceso
                setTimeout(() => {
                    window.location.href = link.href;
                }, 500);
            }
        });
    }
    
    // Función para "seleccionar" un usuario (simbólico)
    async selectUser(userId) {
        try {
            const response = await fetch(`/api/users/${userId}/details`);
            if (response.ok) {
                const userData = await response.json();
                
                // Actualizar usuario "actual"
                this.user = {
                    id: userData.user_info.id,
                    username: userData.user_info.username,
                    role: userData.user_info.role,
                    is_superuser: userData.user_info.is_superuser,
                    authenticated: true // Marcamos como "autenticado" simbólicamente
                };
                
                this.triggerAuthChange();
                
                M.toast({
                    html: `Ahora estás usando como: ${this.user.username} (${this.user.role})`,
                    classes: 'green',
                    displayLength: 4000
                });
                
                return { success: true, user: this.user };
            }
        } catch (error) {
            console.error('Error seleccionando usuario:', error);
        }
        return { success: false, error: 'Usuario no encontrado' };
    }
    
    // Funciones dummy para logout/login
    async logout() {
        // Restablecer a usuario anónimo
        this.user = {
            id: 1,
            username: "anonymous",
            role: "customer",
            is_superuser: false,
            authenticated: false
        };
        
        this.triggerAuthChange();
        
        M.toast({
            html: 'Modo anónimo activado',
            classes: 'blue',
            displayLength: 3000
        });
    }
    
    async login(username, password) {
        // Buscar usuario por nombre
        try {
            const response = await fetch(`/api/users/search?username=${encodeURIComponent(username)}`);
            if (response.ok) {
                const users = await response.json();
                if (users.length > 0) {
                    // Simular "login" seleccionando el primer usuario encontrado
                    return await this.selectUser(users[0].id);
                }
            }
        } catch (error) {
            console.error('Error:', error);
        }
        
        // Si no se encuentra, crear uno nuevo
        M.toast({
            html: 'Usuario no encontrado. Puedes crear uno en /registro',
            classes: 'orange',
            displayLength: 4000
        });
        
        return { success: false, error: 'Usuario no encontrado' };
    }
}

// Crear instancia global
window.authManager = new AuthManager();

// Función dummy para verificar autenticación
function checkAuth() {
    // No verificar nada, permitir todo
    console.log('Autenticación deshabilitada - Acceso libre');
    
    // Ocultar mensajes de "debes iniciar sesión" si existen
    setTimeout(() => {
        const loginMessages = document.querySelectorAll('.login-required-message');
        loginMessages.forEach(msg => msg.style.display = 'none');
    }, 100);
}

// Verificar cuando se carga la página
document.addEventListener('DOMContentLoaded', function() {
    checkAuth();
});

// Exportar para usar en otros scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AuthManager;
}