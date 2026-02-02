# Cerberus CTF - Web PHP Challenge Template
# Supports: PHP 8.2 with Apache/FPM, common CTF web vulnerabilities

FROM php:8.2-apache-bookworm

# Security: Run as non-root
RUN groupadd -r ctf && useradd -r -g ctf -s /bin/false ctf

# Install required packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpng-dev \
    libjpeg-dev \
    libfreetype6-dev \
    libzip-dev \
    libonig-dev \
    libxml2-dev \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install PHP extensions
RUN docker-php-ext-configure gd --with-freetype --with-jpeg \
    && docker-php-ext-install -j$(nproc) \
    gd \
    mysqli \
    pdo_mysql \
    zip \
    mbstring \
    xml \
    opcache

# Configure Apache
RUN a2enmod rewrite headers \
    && echo "ServerTokens Prod" >> /etc/apache2/apache2.conf \
    && echo "ServerSignature Off" >> /etc/apache2/apache2.conf

# Copy challenge files
COPY --chown=ctf:ctf src/ /var/www/html/

# Set permissions
RUN chown -R ctf:ctf /var/www/html \
    && chmod -R 755 /var/www/html \
    && chmod -R 777 /var/www/html/uploads 2>/dev/null || true \
    && chmod -R 777 /var/www/html/tmp 2>/dev/null || true

# Security: Disable dangerous functions
RUN echo "disable_functions = exec,passthru,shell_exec,system,proc_open,popen,curl_exec,curl_multi_exec,parse_ini_file,show_source" >> /usr/local/etc/php/conf.d/security.ini

# Security: PHP hardening
RUN echo "expose_php = Off" >> /usr/local/etc/php/conf.d/security.ini \
    && echo "allow_url_fopen = Off" >> /usr/local/etc/php/conf.d/security.ini \
    && echo "allow_url_include = Off" >> /usr/local/etc/php/conf.d/security.ini \
    && echo "display_errors = Off" >> /usr/local/etc/php/conf.d/security.ini \
    && echo "log_errors = On" >> /usr/local/etc/php/conf.d/security.ini \
    && echo "file_uploads = On" >> /usr/local/etc/php/conf.d/security.ini \
    && echo "upload_max_filesize = 2M" >> /usr/local/etc/php/conf.d/security.ini \
    && echo "post_max_size = 8M" >> /usr/local/etc/php/conf.d/security.ini \
    && echo "max_execution_time = 30" >> /usr/local/etc/php/conf.d/security.ini \
    && echo "memory_limit = 128M" >> /usr/local/etc/php/conf.d/security.ini

# Create tmpfs directories
RUN mkdir -p /tmp/php-sessions /tmp/uploads \
    && chown ctf:ctf /tmp/php-sessions /tmp/uploads

# Switch to non-root user
USER ctf

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:80/health || exit 1

EXPOSE 80

# Start Apache
CMD ["apache2-foreground"]